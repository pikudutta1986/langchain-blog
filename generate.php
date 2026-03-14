<?php

$API_URL  = 'http://localhost:8000/generate';
$category = $_GET['category'] ?? 'artificial intelligence';

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
    die("cURL error: $curlErr");
}

if ($httpCode !== 200) {
    die("API error HTTP $httpCode: $raw");
}

$blog = json_decode($raw, true);

print_r($blog);
