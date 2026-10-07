<?php
// public/index.php
require_once __DIR__ . '/../includes/auth.php';
requireLogin();

$user = currentUser();
$pdo  = getPDO();

// Stats for the current user
$stmt = $pdo->prepare("
    SELECT
        SUM(status = 'pending')  AS pending,
        SUM(status = 'pass')     AS passed,
        SUM(status = 'fail')     AS failed,
        SUM(status = 'blocked')  AS blocked,
        COUNT(*)                 AS total
    FROM test_executions
    WHERE assigned_to = ?
");
$stmt->execute([$user['id']]);
$stats = $stmt->fetch();

// My assigned pending tests
$stmt = $pdo->prepare("
    SELECT e.id, e.status, e.created_at,
           tc.external_id, tc.title, tc.priority, ts.name AS suite_name
    FROM test_executions e
    JOIN test_cases tc ON tc.id = e.test_case_id
    LEFT JOIN test_suites ts ON ts.id = tc.suite_id
    WHERE e.assigned_to = ? AND e.status = 'pending'
    ORDER BY FIELD(tc.priority, 'critical','high','medium','low'), e.created_at
    LIMIT 15
");
$stmt->execute([$user['id']]);
$assigned = $stmt->fetchAll();

$pageTitle = 'Dashboard';
require __DIR__ . '/../includes/header.php';
?>

<!-- Welcome -->
<div class="mb-8">
    <h1 class="text-2xl font-bold text-slate-900">
        Welcome back, <?= htmlspecialchars(explode(' ', $user['full_name'])[0]) ?>
    </h1>
    <p class="mt-1 text-slate-600">Here’s what’s waiting for you today.</p>
</div>

<!-- Stats cards -->
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-10">
    <?php
    $cards = [
        ['label' => 'Pending',  'value' => $stats['pending'] ?? 0, 'color' => 'bg-amber-50 text-amber-700 border-amber-200'],
        ['label' => 'Passed',   'value' => $stats['passed']  ?? 0, 'color' => 'bg-emerald-50 text-emerald-700 border-emerald-200'],
        ['label' => 'Failed',   'value' => $stats['failed']  ?? 0, 'color' => 'bg-rose-50 text-rose-700 border-rose-200'],
        ['label' => 'Total',    'value' => $stats['total']   ?? 0, 'color' => 'bg-sky-50 text-sky-700 border-sky-200'],
    ];
    foreach ($cards as $card):
    ?>
    <div class="rounded-xl border <?= $card['color'] ?> p-5 shadow-sm">
        <p class="text-sm font-medium opacity-80"><?= $card['label'] ?></p>
        <p class="mt-1 text-3xl font-bold"><?= (int)$card['value'] ?></p>
    </div>
    <?php endforeach; ?>
</div>

<!-- Assigned tests -->
<div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
    <div class="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
        <h2 class="text-lg font-semibold text-slate-900">My assigned tests</h2>
        <span class="text-sm text-slate-500"><?= count($assigned) ?> pending</span>
    </div>

    <?php if (empty($assigned)): ?>
        <div class="px-6 py-16 text-center">
            <div class="inline-flex items-center justify-center w-12 h-12 rounded-full bg-slate-100 text-slate-400 mb-4">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
            <p class="text-slate-600 font-medium">You’re all caught up</p>
            <p class="text-sm text-slate-500 mt-1">No pending tests assigned to you right now.</p>
        </div>
    <?php else: ?>
        <ul class="divide-y divide-slate-100">
            <?php foreach ($assigned as $row): ?>
            <li class="px-6 py-4 hover:bg-slate-50 transition flex items-center justify-between gap-4">
                <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2 mb-0.5">
                        <span class="text-xs font-mono font-medium text-slate-500"><?= htmlspecialchars($row['external_id']) ?></span>
                        <?php
                        $prioColor = match($row['priority']) {
                            'critical' => 'bg-rose-100 text-rose-800',
                            'high'     => 'bg-orange-100 text-orange-800',
                            'medium'   => 'bg-sky-100 text-sky-800',
                            default    => 'bg-slate-100 text-slate-700',
                        };
                        ?>
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium <?= $prioColor ?>">
                            <?= ucfirst($row['priority']) ?>
                        </span>
                        <?php if ($row['suite_name']): ?>
                            <span class="text-xs text-slate-400 truncate"><?= htmlspecialchars($row['suite_name']) ?></span>
                        <?php endif; ?>
                    </div>
                    <p class="text-sm font-medium text-slate-900 truncate"><?= htmlspecialchars($row['title']) ?></p>
                </div>
                <a href="/execute.php?id=<?= (int)$row['id'] ?>"
                   class="shrink-0 inline-flex items-center px-3.5 py-1.5 rounded-lg text-sm font-medium bg-sky-600 text-white hover:bg-sky-700 transition">
                    Run
                </a>
            </li>
            <?php endforeach; ?>
        </ul>
    <?php endif; ?>
</div>

<?php require __DIR__ . '/../includes/footer.php'; ?>
