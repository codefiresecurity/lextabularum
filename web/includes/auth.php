<?php
// includes/auth.php

require_once __DIR__ . '/../config/database.php';

session_start();

function currentUser(): ?array
{
    if (empty($_SESSION['user_id'])) {
        return null;
    }

    static $user = null;
    if ($user === null) {
        $stmt = getPDO()->prepare('SELECT id, username, email, full_name, role FROM users WHERE id = ? AND is_active = 1');
        $stmt->execute([$_SESSION['user_id']]);
        $user = $stmt->fetch() ?: null;
        if (!$user) {
            logout();
        }
    }
    return $user;
}

function requireLogin(): void
{
    if (!currentUser()) {
        header('Location: /login.php');
        exit;
    }
}

function login(string $username, string $password): bool
{
    $stmt = getPDO()->prepare('SELECT id, password_hash FROM users WHERE username = ? AND is_active = 1');
    $stmt->execute([$username]);
    $row = $stmt->fetch();

    if ($row && password_verify($password, $row['password_hash'])) {
        session_regenerate_id(true);
        $_SESSION['user_id'] = $row['id'];
        return true;
    }
    return false;
}

function logout(): void
{
    $_SESSION = [];
    if (ini_get('session.use_cookies')) {
        $params = session_get_cookie_params();
        setcookie(session_name(), '', time() - 42000,
            $params['path'], $params['domain'],
            $params['secure'], $params['httponly']
        );
    }
    session_destroy();
}

function isRole(string ...$roles): bool
{
    $user = currentUser();
    return $user && in_array($user['role'], $roles, true);
}
