<?php
// A player's matches, anonymized by their app (contrib.py): one zip, kept until the coach's PC pulls it.
// Checked here: the size, the zip's names (one folder per match, a random id starting with 8, the app's tables), the
// manifest, the counters. Checked again on the coach's PC before anything joins the base (contributions.py).
require __DIR__ . '/_lib.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    reply(405, ['ok' => false, 'error' => 'POST only']);
}
$c = cfg();
$install = (string)($_POST['install'] ?? '');
if (!preg_match('/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/', $install)) {
    reply(400, ['ok' => false, 'error' => 'bad installation id']);
}
$app = substr((string)preg_replace('/[^\w.\-]/', '', (string)($_POST['app'] ?? '')), 0, 40);
$f = $_FILES['file'] ?? null;
if (!$f || ($f['error'] ?? 1) !== UPLOAD_ERR_OK) {
    reply(400, ['ok' => false, 'error' => 'no file']);
}
if ($f['size'] > $c['max_bytes']) {
    reply(413, ['ok' => false, 'error' => 'too big']);
}
if (file_get_contents($f['tmp_name'], false, null, 0, 4) !== "PK\x03\x04") {
    reply(400, ['ok' => false, 'error' => 'not a zip']);
}
$n_matches = null;
if (class_exists('ZipArchive')) {
    $z = new ZipArchive();
    if ($z->open($f['tmp_name']) !== true) {
        reply(400, ['ok' => false, 'error' => 'unreadable zip']);
    }
    $total = 0;
    $ids = [];
    for ($i = 0; $i < $z->numFiles; $i++) {
        $s = $z->statIndex($i);
        $name = $s['name'];
        $total += $s['size'];
        if ($name === 'manifest.json') {
            continue;
        }
        if (!preg_match('#^(8\d{18})/(meta\.json|[a-z_]{3,20}\.parquet)$#', $name, $m)) {
            $z->close();
            reply(400, ['ok' => false, 'error' => 'unexpected file']);
        }
        $ids[$m[1]] = true;
    }
    $man = json_decode((string)$z->getFromName('manifest.json'), true);
    $z->close();
    if (!is_array($man) || ($man['install'] ?? '') !== $install || $total > 8 * $c['max_bytes'] || !$ids || count($ids) > 60) {
        reply(400, ['ok' => false, 'error' => 'bad content']);
    }
    $n_matches = count($ids);
}
$d = data_dir();
if (!count_up($d, 'install:' . $install, (int)$c['per_day']) || !count_up($d, ip_key($d), (int)$c['per_ip_day'])) {
    reply(429, ['ok' => false, 'error' => 'enough for today']);
}
$name = gmdate('YmdHis') . '-' . bin2hex(random_bytes(6));
if (!move_uploaded_file($f['tmp_name'], "$d/incoming/$name.zip")) {
    reply(500, ['ok' => false, 'error' => 'not stored']);
}
@file_put_contents("$d/incoming/$name.json", json_encode(['install' => $install, 'app' => $app, 'size' => $f['size'],
    'matches' => $n_matches, 'at' => time()]));
reply(200, ['ok' => true, 'id' => $name, 'matches' => $n_matches]);
