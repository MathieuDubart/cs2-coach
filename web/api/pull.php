<?php
// The coach's PC pulls what players sent (contributions.py): its token in the X-Coach-Token header, compared with the
// hash in config.php. kind=contrib (the shared matches, zips; the default) or kind=reports (bug reports, json).
// action=list -> the waiting files; action=get&f= -> one file; action=delete&f= (POST) -> removed once pulled.
require __DIR__ . '/_lib.php';

$c = cfg();
$tok = (string)($_SERVER['HTTP_X_COACH_TOKEN'] ?? '');
if ($c['token_sha256'] === '' || $tok === '' || !hash_equals($c['token_sha256'], hash('sha256', $tok))) {
    reply(403, ['ok' => false, 'error' => 'forbidden']);
}
$kind = (string)($_GET['kind'] ?? 'contrib');
if ($kind === 'reports') {
    $in = data_dir() . '/reports';
    $ext = 'json';
} else {
    $in = data_dir() . '/incoming';
    $ext = 'zip';
}
if (!is_dir($in)) {
    @mkdir($in, 0700, true);
}
$action = (string)($_GET['action'] ?? 'list');
$file = basename((string)($_GET['f'] ?? ''));
if ($action !== 'list' && !preg_match('/^\d{14}-[0-9a-f]{12}\.' . $ext . '$/', $file)) {
    reply(400, ['ok' => false, 'error' => 'bad file name']);
}
if ($action === 'list') {
    $out = [];
    foreach (glob("$in/*.$ext") ?: [] as $p) {
        $meta = $ext === 'zip' ? (json_decode((string)@file_get_contents(substr($p, 0, -4) . '.json'), true) ?: []) : [];
        $out[] = ['f' => basename($p), 'size' => filesize($p), 'sha256' => hash_file('sha256', $p), 'meta' => $meta];
    }
    reply(200, ['ok' => true, 'files' => $out]);
}
if ($action === 'get') {
    $p = "$in/$file";
    if (!is_file($p)) {
        reply(404, ['ok' => false, 'error' => 'not found']);
    }
    header('Content-Type: ' . ($ext === 'zip' ? 'application/zip' : 'application/json'));
    header('Content-Length: ' . filesize($p));
    header('Cache-Control: no-store');
    readfile($p);
    exit;
}
if ($action === 'delete' && ($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
    @unlink("$in/$file");
    if ($ext === 'zip') {
        @unlink(substr("$in/$file", 0, -4) . '.json');
    }
    reply(200, ['ok' => true]);
}
reply(400, ['ok' => false, 'error' => 'unknown action']);
