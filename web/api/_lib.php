<?php
// Coach CS2's API on wily.valentingassend.com (05/10): the matches players share anonymized (contribute.php), pulled
// by the coach's PC (pull.php). config.php, written by `python contributions.py init`, holds the hash of the coach's
// token (the token itself stays on his PC). No database: files in a folder the web never serves.
declare(strict_types=1);

function cfg(): array
{
    static $c = null;
    if ($c === null) {
        $f = __DIR__ . '/config.php';
        $c = is_file($f) ? (require $f) : [];
        $c += ['token_sha256' => '', 'max_bytes' => 25 * 1024 * 1024, 'per_day' => 40, 'per_ip_day' => 80, 'data' => null];
        // the coach's Steam Web API key for steam.php (08/10): written at the site's build from his settings, never versioned
        $k = __DIR__ . '/steam_key.php';
        $c += ['steam_key' => is_file($k) ? (string)(require $k) : ''];
    }
    return $c;
}

function reply(int $code, array $body)
{
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    echo json_encode($body);
    exit;
}

// outside the site's folder when the hosting allows it, else a folder of the site the web server refuses to serve
function data_dir(): string
{
    $c = cfg();
    foreach ([$c['data'], dirname(__DIR__, 2) . '/wily-data', dirname(__DIR__) . '/data'] as $d) {
        if (!$d) {
            continue;
        }
        if (!is_dir($d)) {
            @mkdir($d, 0700, true);
        }
        if (is_dir($d) && is_writable($d)) {
            if (!is_dir("$d/incoming")) {
                @mkdir("$d/incoming", 0700, true);
            }
            if (!is_file("$d/.htaccess")) {
                @file_put_contents("$d/.htaccess", "Require all denied\n");
            }
            return $d;
        }
    }
    reply(500, ['ok' => false, 'error' => 'storage unavailable']);
}

// small counters per day (a flood refused), with a lock: one file per day, the old ones removed
function count_up(string $dir, string $key, int $limit): bool
{
    $day = gmdate('Ymd');
    $f = "$dir/count-$day.json";
    $h = fopen($f, 'c+');
    if (!$h) {
        return true;
    }
    flock($h, LOCK_EX);
    $raw = stream_get_contents($h);
    $all = $raw ? (json_decode($raw, true) ?: []) : [];
    $n = ($all[$key] ?? 0) + 1;
    $ok = $n <= $limit;
    if ($ok) {
        $all[$key] = $n;
        ftruncate($h, 0);
        rewind($h);
        fwrite($h, json_encode($all));
    }
    flock($h, LOCK_UN);
    fclose($h);
    foreach (glob("$dir/count-*.json") ?: [] as $old) {
        if ($old !== $f && filemtime($old) < time() - 2 * 86400) {
            @unlink($old);
        }
    }
    foreach (glob("$dir/salt-*") ?: [] as $old) {
        if (basename($old) !== "salt-$day" && filemtime($old) < time() - 2 * 86400) {
            @unlink($old);
        }
    }
    return $ok;
}

// the sender's address is never kept: a hash with a salt of the day (deleted after two days), for the counters only
function ip_key(string $dir): string
{
    $f = "$dir/salt-" . gmdate('Ymd');
    if (!is_file($f)) {
        @file_put_contents($f, bin2hex(random_bytes(16)));
    }
    return 'ip:' . substr(hash('sha256', (string)@file_get_contents($f) . ($_SERVER['REMOTE_ADDR'] ?? '')), 0, 24);
}
