<?php
// includes/header.php
$user = currentUser();
?>
<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= htmlspecialchars($pageTitle ?? 'Dashboard') ?> · Lex Tabularum</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        brand: {
                            50:  '#f0f9ff',
                            100: '#e0f2fe',
                            500: '#0ea5e9',
                            600: '#0284c7',
                            700: '#0369a1',
                            900: '#0c4a6e',
                        }
                    }
                }
            }
        }
    </script>
    <style>
        body { font-family: 'Inter', system-ui, sans-serif; }
    </style>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body class="h-full bg-slate-50 text-slate-800">
<div class="min-h-full">
    <!-- Top navigation -->
    <nav class="bg-white border-b border-slate-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center gap-3">
                    <div class="flex items-center justify-center w-9 h-9 rounded-lg bg-brand-600 text-white font-bold text-lg">
                        LT
                    </div>
                    <span class="text-xl font-semibold tracking-tight text-slate-900">Lex Tabularum</span>
                </div>

                <?php if ($user): ?>
                <div class="flex items-center gap-6">
                    <span class="text-sm text-slate-600">
                        <?= htmlspecialchars($user['full_name']) ?>
                        <span class="ml-1 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
                            <?= $user['role'] === 'admin' ? 'bg-purple-100 text-purple-800' :
                               ($user['role'] === 'lead' ? 'bg-amber-100 text-amber-800' : 'bg-sky-100 text-sky-800') ?>">
                            <?= ucfirst($user['role']) ?>
                        </span>
                    </span>
                    <a href="/logout.php" class="text-sm font-medium text-slate-500 hover:text-slate-900 transition">
                        Sign out
                    </a>
                </div>
                <?php endif; ?>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
