<?php
// Anonymous usage statistics (05/10, the alpha): one report per app and per day, counters only (the pages opened and
// the time on each, the buttons used, the page's errors, the time Live ran during a match, the app's version, a
// screen size class): no identifier, no SteamID, no name, nothing written by the player. Each report is added to
// that day's totals and thrown away: only sums per day are kept (data/usage/<day>.json), read by the coach's PC
// (pull.php?kind=usage) to see what players use and what they don't.
require __DIR__ . '/_lib.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    reply(405, ['ok' => false, 'error' => 'POST only']);
}
$raw = (string)file_get_contents('php://input', false, null, 0, 96 * 1024 + 1);
if (strlen($raw) > 96 * 1024) {
    reply(413, ['ok' => false, 'error' => 'too big']);
}
$r = json_decode($raw, true);
if (!is_array($r)) {
    reply(400, ['ok' => false, 'error' => 'not a report']);
}
$day = (string)($r['day'] ?? '');
$t = strtotime($day . ' 12:00:00 UTC');
if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $day) || $t === false || $t < time() - 9 * 86400 || $t > time() + 2 * 86400) {
    reply(400, ['ok' => false, 'error' => 'bad day']);
}
$num = function ($v, int $max): int {
    return is_numeric($v) ? max(0, min($max, (int)$v)) : 0;
};
$views = [];
foreach ((is_array($r['views'] ?? null) ? $r['views'] : []) as $k => $v) {
    if (count($views) >= 80 || !preg_match('/^[a-z0-9_.:-]{1,40}$/', (string)$k) || !is_array($v)) {
        continue;
    }
    $views[$k] = ['visits' => $num($v['visits'] ?? 0, 5000), 'seconds' => $num($v['seconds'] ?? 0, 86400)];
}
$actions = [];
foreach ((is_array($r['actions'] ?? null) ? $r['actions'] : []) as $k => $v) {
    if (count($actions) >= 300 || !preg_match('/^[A-Za-z0-9_.:#=\[\]\/-]{1,80}$/', (string)$k)) {
        continue;
    }
    $actions[$k] = $num($v, 10000);
}
$errors = $num($r['errors'] ?? 0, 10000);
$live = $num($r['live'] ?? 0, 86400);
$screen = in_array($r['screen'] ?? '', ['phone', 'tablet', 'laptop', 'desktop', 'wide'], true) ? $r['screen'] : 'unknown';
$app = substr((string)preg_replace('/[^\w.\-]/', '', (string)($r['app'] ?? '')), 0, 40) ?: 'unknown';

$d = data_dir();
if (!count_up($d, ip_key($d) . ':usage', 6)) {
    reply(429, ['ok' => false, 'error' => 'enough for today']);
}
if (!is_dir("$d/usage")) {
    @mkdir("$d/usage", 0700, true);
}
$f = "$d/usage/$day.json";
$h = fopen($f, 'c+');
if (!$h) {
    reply(500, ['ok' => false, 'error' => 'not stored']);
}
flock($h, LOCK_EX);
$cur = stream_get_contents($h);
$tot = $cur ? (json_decode($cur, true) ?: []) : [];
$tot += ['day' => $day, 'reports' => 0, 'views' => [], 'actions' => [], 'errors' => 0, 'error_reports' => 0,
    'live' => ['users' => 0, 'seconds' => 0], 'apps' => [], 'screens' => []];
$tot['reports']++;
foreach ($views as $k => $v) {
    $x = $tot['views'][$k] ?? ['users' => 0, 'visits' => 0, 'seconds' => 0];
    $tot['views'][$k] = ['users' => $x['users'] + 1, 'visits' => $x['visits'] + $v['visits'], 'seconds' => $x['seconds'] + $v['seconds']];
}
foreach ($actions as $k => $n) {
    $x = $tot['actions'][$k] ?? ['users' => 0, 'count' => 0];
    $tot['actions'][$k] = ['users' => $x['users'] + 1, 'count' => $x['count'] + $n];
}
$tot['errors'] += $errors;
$tot['error_reports'] += $errors > 0 ? 1 : 0;
if ($live > 0) {
    $tot['live'] = ['users' => $tot['live']['users'] + 1, 'seconds' => $tot['live']['seconds'] + $live];
}
$tot['apps'][$app] = ($tot['apps'][$app] ?? 0) + 1;
$tot['screens'][$screen] = ($tot['screens'][$screen] ?? 0) + 1;
ftruncate($h, 0);
rewind($h);
fwrite($h, json_encode($tot, JSON_UNESCAPED_SLASHES));
flock($h, LOCK_UN);
fclose($h);
reply(200, ['ok' => true]);
