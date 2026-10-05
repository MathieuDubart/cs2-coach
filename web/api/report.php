<?php
// A bug report from a player's app (bugreport.py, 05/10, the alpha): what happened, what they expected, an email
// address only if they gave one, and the technical details they chose to include (they see them before sending).
// Kept until the coach's PC pulls it (pull.php?kind=reports), then deleted here.
require __DIR__ . '/_lib.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    reply(405, ['ok' => false, 'error' => 'POST only']);
}
$raw = (string)file_get_contents('php://input', false, null, 0, 700 * 1024 + 1);
if (strlen($raw) > 700 * 1024) {
    reply(413, ['ok' => false, 'error' => 'too big']);
}
$r = json_decode($raw, true);
if (!is_array($r)) {
    reply(400, ['ok' => false, 'error' => 'not a report']);
}
$install = (string)($r['install'] ?? '');
if (!preg_match('/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/', $install)) {
    reply(400, ['ok' => false, 'error' => 'bad installation id']);
}
$text = trim((string)($r['text'] ?? ''));
if ($text === '' || strlen($text) > 20000) {
    reply(400, ['ok' => false, 'error' => 'the description is empty or too long']);
}
$email = trim((string)($r['email'] ?? ''));
if ($email !== '' && (strlen($email) > 200 || !filter_var($email, FILTER_VALIDATE_EMAIL))) {
    reply(400, ['ok' => false, 'error' => 'that email address does not look right']);
}
$diag = $r['diag'] ?? null;
if ($diag !== null && !is_array($diag)) {
    reply(400, ['ok' => false, 'error' => 'bad details']);
}
$kind = in_array($r['kind'] ?? 'bug', ['bug', 'idea'], true) ? $r['kind'] ?? 'bug' : 'bug';
$d = data_dir();
if (!count_up($d, 'report:' . $install, 10) || !count_up($d, ip_key($d) . ':report', 20)) {
    reply(429, ['ok' => false, 'error' => 'enough reports for today, thank you']);
}
if (!is_dir("$d/reports")) {
    @mkdir("$d/reports", 0700, true);
}
$name = gmdate('YmdHis') . '-' . bin2hex(random_bytes(6));
$ok = @file_put_contents("$d/reports/$name.json", json_encode([
    'id' => $name, 'at' => time(), 'kind' => $kind, 'install' => $install,
    'app' => substr((string)preg_replace('/[^\w.\-]/', '', (string)($r['app'] ?? '')), 0, 40),
    'text' => $text, 'expected' => substr(trim((string)($r['expected'] ?? '')), 0, 8000),
    'email' => $email, 'page' => substr((string)($r['page'] ?? ''), 0, 120), 'diag' => $diag,
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
if ($ok === false) {
    reply(500, ['ok' => false, 'error' => 'not stored']);
}
reply(200, ['ok' => true, 'id' => $name]);
