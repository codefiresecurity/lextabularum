<?php
// Router for PHP's development server. Production routing belongs in Nginx.
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
if (str_starts_with($path, '/api/')) {
    $target = 'http://127.0.0.1:8000' . $_SERVER['REQUEST_URI'];
    $headers = [];
    foreach (getallheaders() as $name => $value) {
        if (!in_array(strtolower($name), ['host', 'content-length', 'content-type'])) $headers[] = "$name: $value";
    }
    $requestBody = file_get_contents('php://input');
    if ($_FILES) {
        $requestBody = $_POST;
        foreach ($_FILES as $name => $upload) {
            $requestBody[$name] = new CURLFile($upload['tmp_name'], $upload['type'], $upload['name']);
        }
    } elseif (isset($_SERVER['CONTENT_TYPE'])) {
        $headers[] = 'Content-Type: ' . $_SERVER['CONTENT_TYPE'];
    }
    $ch = curl_init($target);
    curl_setopt_array($ch, [
        CURLOPT_CUSTOMREQUEST => $_SERVER['REQUEST_METHOD'],
        CURLOPT_HTTPHEADER => $headers,
        CURLOPT_POSTFIELDS => $requestBody,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HEADER => true,
        CURLOPT_FOLLOWLOCATION => false,
    ]);
    $response = curl_exec($ch);
    $headerSize = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
    $status = curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    if ($response === false) {
        http_response_code(502);
        echo 'Development API proxy failed: ' . curl_error($ch);
        curl_close($ch);
        return true;
    }
    http_response_code($status);
    foreach (explode("\r\n", substr($response, 0, $headerSize)) as $header) {
        $lower = strtolower($header);
        if (str_contains($header, ':') && !str_starts_with($lower, 'content-length:') && !str_starts_with($lower, 'transfer-encoding:')) {
            header($header, false);
        }
    }
    $body = substr($response, $headerSize);
    curl_close($ch);
    echo $body;
    return true;
}
$file = __DIR__ . $path;
if ($path !== '/' && is_file($file)) return false;
require __DIR__ . '/index.php';
