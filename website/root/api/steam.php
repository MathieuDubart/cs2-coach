<?php
declare(strict_types=1);
// Steam for the players' apps (08/10, the user: one code to paste, no Steam Web API key of their own to create): this
// site's key asks Steam three things for them. The next match of their history (their history code comes in the body
// of the request, is used for that request only and never written anywhere), persona names and a friend list (public
// data). Nothing is kept but daily counters (the sender's address as a hash with a salt of the day, see _lib.php).
require __DIR__ . '/_lib.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    reply(405, ['ok' => false, 'error' => 'POST only']);
}
$key = (string)(cfg()['steam_key'] ?? '');
if (!preg_match('/^[0-9A-Fa-f]{32}$/', $key)) {
    reply(503, ['ok' => false, 'error' => 'the Steam relay is not set up']);
}
$raw = (string)file_get_contents('php://input', false, null, 0, 8193);
if (strlen($raw) > 8192) {
    reply(413, ['ok' => false, 'error' => 'too big']);
}
$r = json_decode($raw, true);
if (!is_array($r)) {
    reply(400, ['ok' => false, 'error' => 'not a request']);
}
$op = (string)($r['op'] ?? '');
$limits = ['next' => 4000, 'names' => 400, 'friends' => 200];   // per address and day: a whole history walk fits
if (!isset($limits[$op])) {
    reply(400, ['ok' => false, 'error' => 'unknown question']);
}
$d = data_dir();
// Steam allows 100,000 calls a day per key: the relay stops before
if (!count_up($d, ip_key($d) . ':steam-' . $op, $limits[$op]) || !count_up($d, 'steam-all', 90000)) {
    reply(429, ['ok' => false, 'error' => 'enough Steam questions for today']);
}

function steam(string $key, string $path, array $q): array
{
    $ch = curl_init('https://api.steampowered.com/' . $path . '?' . http_build_query(['key' => $key] + $q));
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20, CURLOPT_CONNECTTIMEOUT => 8,
                            CURLOPT_USERAGENT => 'wily-relay', CURLOPT_FOLLOWLOCATION => false]);
    $body = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    $j = is_string($body) ? json_decode($body, true) : null;
    return [$code, is_array($j) ? $j : null];
}

function is_sid(string $s): bool
{
    return (bool)preg_match('/^7656\d{13}$/', $s);
}

$sid = (string)($r['steamid'] ?? '');
if ($op === 'next') {
    $auth = strtoupper((string)($r['auth'] ?? ''));
    $known = (string)($r['known'] ?? '');
    if (!is_sid($sid) || !preg_match('/^[A-Z0-9]{4}-[A-Z0-9]{5}-[A-Z0-9]{4}$/', $auth) || !preg_match('/^CSGO(-[A-Za-z0-9]{5}){5}$/', $known)) {
        reply(400, ['ok' => false, 'error' => 'bad SteamID, history code or match code']);
    }
    [$code, $j] = steam($key, 'ICSGOPlayers_730/GetNextMatchSharingCode/v1', ['steamid' => $sid, 'steamidkey' => $auth, 'knowncode' => $known]);
    $next = $j['result']['nextcode'] ?? null;
    reply(200, ['ok' => true, 'status' => $code, 'nextcode' => is_string($next) ? $next : null]);
}
if ($op === 'names') {
    $ids = array_values(array_filter(array_map('strval', (array)($r['steamids'] ?? [])), 'is_sid'));
    if (!$ids || count($ids) > 100) {
        reply(400, ['ok' => false, 'error' => '1 to 100 SteamIDs']);
    }
    [$code, $j] = steam($key, 'ISteamUser/GetPlayerSummaries/v2/', ['steamids' => implode(',', $ids)]);
    $out = [];
    foreach (($j['response']['players'] ?? []) as $p) {
        $out[] = ['steamid' => (string)($p['steamid'] ?? ''), 'personaname' => (string)($p['personaname'] ?? ''),
                  'avatarfull' => (string)($p['avatarfull'] ?? '')];
    }
    reply(200, ['ok' => true, 'status' => $code, 'players' => $out]);
}
// friends: a public friend list, the SteamIDs only
if (!is_sid($sid)) {
    reply(400, ['ok' => false, 'error' => 'bad SteamID']);
}
[$code, $j] = steam($key, 'ISteamUser/GetFriendList/v1/', ['steamid' => $sid, 'relationship' => 'friend']);
$ids = [];
foreach (($j['friendslist']['friends'] ?? []) as $f) {
    $ids[] = (string)($f['steamid'] ?? '');
}
reply(200, ['ok' => true, 'status' => $code, 'friends' => $ids]);
