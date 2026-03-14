<?php
/**
 * AI Blog Generator – WordPress Post Inserter
 *
 * Place this file at the WordPress root (same folder as wp-load.php).
 * Call it via browser or cron:
 *   http://your-site.com/generate.php?category=artificial+intelligence
 *
 * Set DEBUG_MODE to true temporarily to see the real PHP/WP error message.
 */

// ── Debug mode — set true to see real errors, false on production ─────────────
define('DEBUG_MODE', true);

if (DEBUG_MODE) {
    ini_set('display_errors', '1');
    ini_set('display_startup_errors', '1');
    error_reporting(E_ALL);
}

// ── Raise limits for long-running AI pipeline ─────────────────────────────────
set_time_limit(0);                       // no PHP execution timeout
ini_set('memory_limit', '512M');         // base64 image data can be large

// ── Bootstrap WordPress ───────────────────────────────────────────────────────
require_once __DIR__ . '/wp-load.php';

// ── Config ────────────────────────────────────────────────────────────────────
// IMPORTANT for remote servers:
// Change this to the actual IP / hostname where the Docker API is running.
// e.g. 'http://192.168.1.10:8000/generate'  or  'http://api.your-domain.com/generate'
// Do NOT use 'localhost' if the API runs on a different machine than this WordPress site.
$API_URL  = defined('BLOG_API_URL') ? BLOG_API_URL : 'http://localhost:8000/generate';
$category = sanitize_text_field($_GET['category'] ?? 'artificial intelligence');

    
// ── 1. Call the API ───────────────────────────────────────────────────────────
$ch = curl_init($API_URL);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST           => true,
    CURLOPT_POSTFIELDS     => json_encode(['category' => $category]),
    CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
    CURLOPT_TIMEOUT        => 0,         // no cURL timeout (pipeline can take minutes)
    CURLOPT_CONNECTTIMEOUT => 10,        // fail fast if the API host is unreachable
]);
$raw      = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$curlErr  = curl_error($ch);
curl_close($ch);

if ($curlErr) {
    wp_die(
        '<strong>cURL error — is the API reachable?</strong><br>'
        . esc_html($curlErr)
        . '<br><br>API URL tried: <code>' . esc_html($API_URL) . '</code>'
    );
}

if ($httpCode !== 200) {
    wp_die(
        '<strong>API returned HTTP ' . (int) $httpCode . '</strong><br>'
        . esc_html($raw)
    );
}

$blog = json_decode($raw, true);
if (!$blog || empty($blog['title']) || empty($blog['content'])) {
    wp_die('Invalid or empty response from API: ' . esc_html($raw));
}

// ── 2. Convert Markdown → HTML ────────────────────────────────────────────────
$post_content = markdown_to_html($blog['content']);

// ── 3. Resolve / create WordPress category ───────────────────────────────────
// wp_create_category() lives in wp-admin/includes/taxonomy.php which is not
// loaded automatically by wp-load.php — require it explicitly.
require_once ABSPATH . 'wp-admin/includes/taxonomy.php';

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
$featured_image_id  = null;
$featured_image_url = null;
$image_error        = null;

if (!empty($blog['image_base64'])) {
    $image_bytes = base64_decode($blog['image_base64']);

    if ($image_bytes === false) {
        $image_error = 'base64_decode failed.';
    } else {
        $filename = sanitize_file_name($blog['image_filename'] ?? ('blog-' . $post_id . '.png'));
        $upload   = wp_upload_bits($filename, null, $image_bytes);

        if (!empty($upload['error'])) {
            $image_error = 'wp_upload_bits error: ' . $upload['error'];
        } else {
            $attachment_id = wp_insert_attachment([
                'post_mime_type' => 'image/png',
                'post_title'     => sanitize_file_name($filename),
                'post_content'   => '',
                'post_status'    => 'inherit',
            ], $upload['file'], $post_id);

            if (is_wp_error($attachment_id)) {
                $image_error = 'wp_insert_attachment error: ' . $attachment_id->get_error_message();
            } else {
                require_once ABSPATH . 'wp-admin/includes/image.php';
                $meta = wp_generate_attachment_metadata($attachment_id, $upload['file']);
                wp_update_attachment_metadata($attachment_id, $meta);
                set_post_thumbnail($post_id, $attachment_id);

                $featured_image_id  = $attachment_id;
                $featured_image_url = wp_get_attachment_url($attachment_id);
            }
        }
    }
}

// ── 6. Print result ───────────────────────────────────────────────────────────
print_r([
    'status'             => 'success',
    'post_id'            => $post_id,
    'post_url'           => get_permalink($post_id),
    'title'              => $blog['title'],
    'category'           => $cat_name,
    'topic'              => $blog['topic'],
    'summary'            => $blog['summary'],
    'featured_image_id'  => $featured_image_id,
    'featured_image_url' => $featured_image_url,
    'image_error'        => $image_error,   // null = image uploaded fine
]);

// ── Markdown → HTML ───────────────────────────────────────────────────────────
function markdown_to_html(string $md): string
{
    $lines   = explode("\n", $md);
    $html    = '';
    $inList  = false;
    $inCode  = false;
    $codeBuf = '';

    foreach ($lines as $line) {
        if (str_starts_with(trim($line), '```')) {
            if ($inCode) {
                $html   .= '<pre><code>' . esc_html($codeBuf) . '</code></pre>';
                $codeBuf = ''; $inCode = false;
            } else {
                if ($inList) { $html .= '</ul>'; $inList = false; }
                $inCode = true;
            }
            continue;
        }
        if ($inCode) { $codeBuf .= $line . "\n"; continue; }

        $trimmed = trim($line);
        if ($inList && !preg_match('/^[-*\d]/', $trimmed)) {
            $html .= '</ul>'; $inList = false;
        }
        if (preg_match('/^(#{1,6})\s+(.+)/', $line, $m)) {
            $l = strlen($m[1]);
            $html .= "<h{$l}>" . inline_md($m[2]) . "</h{$l}>\n";
        } elseif (preg_match('/^[-*]\s+(.+)/', $line, $m)) {
            if (!$inList) { $html .= '<ul>'; $inList = true; }
            $html .= '<li>' . inline_md($m[1]) . '</li>';
        } elseif (preg_match('/^\d+\.\s+(.+)/', $line, $m)) {
            if (!$inList) { $html .= '<ul>'; $inList = true; }
            $html .= '<li>' . inline_md($m[1]) . '</li>';
        } elseif (str_starts_with($trimmed, '> ')) {
            $html .= '<blockquote>' . inline_md(substr($trimmed, 2)) . '</blockquote>';
        } elseif ($trimmed === '') {
            $html .= "\n";
        } else {
            $html .= '<p>' . inline_md($trimmed) . "</p>\n";
        }
    }
    if ($inList) $html .= '</ul>';
    return $html;
}

function inline_md(string $t): string
{
    $t = esc_html($t);
    $t = preg_replace('/\*\*\*(.+?)\*\*\*/', '<strong><em>$1</em></strong>', $t);
    $t = preg_replace('/\*\*(.+?)\*\*/',     '<strong>$1</strong>',          $t);
    $t = preg_replace('/\*(.+?)\*/',          '<em>$1</em>',                 $t);
    $t = preg_replace('/`([^`]+)`/',           '<code>$1</code>',             $t);
    $t = preg_replace('/\[([^\]]+)\]\(([^)]+)\)/', '<a href="$2">$1</a>',    $t);
    return $t;
}
