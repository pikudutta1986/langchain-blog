<?php
/**
 * AI Blog Generator – WordPress Post Inserter
 *
 * Place this file at the WordPress root (same folder as wp-load.php).
 * Call it via browser or cron:
 *   http://your-site.com/generate.php?category=artificial+intelligence
 *
 * What it does:
 *   1. Calls the LangChain /generate API
 *   2. Converts the Markdown content to HTML
 *   3. Creates a WordPress post (Published)
 *   4. Decodes image_base64 → uploads to WordPress Media Library
 *   5. Sets the uploaded image as the post's Featured Image
 */

// ── Bootstrap WordPress ───────────────────────────────────────────────────────
require_once __DIR__ . '/wp-load.php';

// ── Config ────────────────────────────────────────────────────────────────────
$API_URL  = 'http://localhost:8000/generate';   // adjust if API runs elsewhere
$category = sanitize_text_field($_GET['category'] ?? 'artificial intelligence');

// ── 1. Call the API ───────────────────────────────────────────────────────────
$ch = curl_init($API_URL);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST           => true,
    CURLOPT_POSTFIELDS     => json_encode(['category' => $category]),
    CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
    CURLOPT_TIMEOUT        => 300,
]);
$raw      = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$curlErr  = curl_error($ch);
curl_close($ch);

if ($curlErr) {
    wp_die("cURL error: " . esc_html($curlErr));
}
if ($httpCode !== 200) {
    wp_die("API returned HTTP $httpCode: " . esc_html($raw));
}

$blog = json_decode($raw, true);
if (!$blog || empty($blog['title']) || empty($blog['content'])) {
    wp_die('Invalid response from API: ' . esc_html($raw));
}

// ── 2. Convert Markdown → HTML ────────────────────────────────────────────────
$post_content = markdown_to_html($blog['content']);

// ── 3. Resolve / create WordPress category ───────────────────────────────────
$cat_name = ucwords($blog['category']);
$cat_id   = get_cat_ID($cat_name);
if (!$cat_id) {
    $cat_id = wp_create_category($cat_name);
}


// ── 4. Insert WordPress post ──────────────────────────────────────────────────
$post_id = wp_insert_post([
    'post_title'    => wp_strip_all_tags($blog['title']),
    'post_content'  => $post_content,
    'post_excerpt'  => wp_strip_all_tags($blog['summary']),
    'post_status'   => 'publish',
    'post_type'     => 'post',
    'post_category' => [$cat_id],
    'tags_input'    => [$blog['topic']],
], true);

if (is_wp_error($post_id)) {
    wp_die('Failed to create post: ' . esc_html($post_id->get_error_message()));
}

// ── 5. Upload image_base64 → WordPress Media Library → Featured Image ─────────
$featured_image_id = null;

if (!empty($blog['image_base64'])) {
    $image_bytes = base64_decode($blog['image_base64']);
    $filename    = sanitize_file_name($blog['image_filename'] ?? ('blog-' . $post_id . '.png'));

    // Save to WordPress uploads directory
    $upload = wp_upload_bits($filename, null, $image_bytes);

    if (empty($upload['error'])) {
        // Create the attachment record
        $attachment_id = wp_insert_attachment([
            'post_mime_type' => 'image/png',
            'post_title'     => sanitize_file_name($filename),
            'post_content'   => '',
            'post_status'    => 'inherit',
        ], $upload['file'], $post_id);

        // Generate all registered image sizes (thumbnail, medium, large…)
        require_once ABSPATH . 'wp-admin/includes/image.php';
        $attach_metadata = wp_generate_attachment_metadata($attachment_id, $upload['file']);
        wp_update_attachment_metadata($attachment_id, $attach_metadata);

        // Set as Featured Image (post thumbnail)
        set_post_thumbnail($post_id, $attachment_id);
        $featured_image_id = $attachment_id;
    }
}

// ── 6. Print result ───────────────────────────────────────────────────────────
print_r([
    'post_id'           => $post_id,
    'post_url'          => get_permalink($post_id),
    'title'             => $blog['title'],
    'category'          => $cat_name,
    'topic'             => $blog['topic'],
    'summary'           => $blog['summary'],
    'featured_image_id' => $featured_image_id,
    'featured_image_url'=> $featured_image_id ? wp_get_attachment_url($featured_image_id) : null,
]);

// ────────────────────────────────────────────────────────────────────────────
// Markdown → HTML  (no external library needed)
// ────────────────────────────────────────────────────────────────────────────
function markdown_to_html(string $md): string
{
    $lines   = explode("\n", $md);
    $html    = '';
    $inList  = false;
    $inCode  = false;
    $codeBuf = '';

    foreach ($lines as $line) {

        // Fenced code blocks
        if (str_starts_with(trim($line), '```')) {
            if ($inCode) {
                $html   .= '<pre><code>' . esc_html($codeBuf) . '</code></pre>';
                $codeBuf = '';
                $inCode  = false;
            } else {
                if ($inList) { $html .= '</ul>'; $inList = false; }
                $inCode = true;
            }
            continue;
        }
        if ($inCode) { $codeBuf .= $line . "\n"; continue; }

        $trimmed = trim($line);

        // Close open list before block elements
        if ($inList && !preg_match('/^[-*\d]/', $trimmed)) {
            $html  .= '</ul>';
            $inList = false;
        }

        // Headings
        if (preg_match('/^(#{1,6})\s+(.+)/', $line, $m)) {
            $level = strlen($m[1]);
            $html .= "<h{$level}>" . inline($m[2]) . "</h{$level}>\n";
            continue;
        }

        // Unordered list
        if (preg_match('/^[-*]\s+(.+)/', $line, $m)) {
            if (!$inList) { $html .= '<ul>'; $inList = true; }
            $html .= '<li>' . inline($m[1]) . '</li>';
            continue;
        }

        // Ordered list
        if (preg_match('/^\d+\.\s+(.+)/', $line, $m)) {
            if (!$inList) { $html .= '<ul>'; $inList = true; }
            $html .= '<li>' . inline($m[1]) . '</li>';
            continue;
        }

        // Blockquote
        if (str_starts_with($trimmed, '> ')) {
            $html .= '<blockquote>' . inline(substr($trimmed, 2)) . '</blockquote>';
            continue;
        }

        // Blank line
        if ($trimmed === '') { $html .= "\n"; continue; }

        // Paragraph
        $html .= '<p>' . inline($trimmed) . "</p>\n";
    }

    if ($inList) $html .= '</ul>';

    return $html;
}

function inline(string $text): string
{
    $text = esc_html($text);
    $text = preg_replace('/\*\*\*(.+?)\*\*\*/', '<strong><em>$1</em></strong>', $text);
    $text = preg_replace('/\*\*(.+?)\*\*/',     '<strong>$1</strong>',          $text);
    $text = preg_replace('/\*(.+?)\*/',          '<em>$1</em>',                 $text);
    $text = preg_replace('/`([^`]+)`/',           '<code>$1</code>',             $text);
    $text = preg_replace('/\[([^\]]+)\]\(([^)]+)\)/', '<a href="$2">$1</a>',    $text);
    return $text;
}
