# AUTOPILOT CONSTITUTION v4.2
(Status: FINAL · Binding)

## Назначение
Документ фиксирует правила автопилота для проекта.
Все изменения должны соответствовать этому документу.
Чаты не являются источником истины.

## Роли
- AI: автор изменений (только artifacts → CI → PR)
- CI: надсмотрщик (гейты и блокировки)
- Human: финальный арбитр (approve / deny)

## Backup
- Тег: manual-last-stable
- Неприкосновенен
- Откат = checkout тега + MODE: manual

## Sandbox
- Все автопилотные итерации только в sandbox
- Branch: ai-sandbox/*
- Environment: live-apply-sandbox

### Triple Guard
1) branch guard (ai-sandbox/*)
2) environment guard (live-apply-sandbox)
3) fail-fast если main

## Итерационный цикл
- 1 PR = 1 причина
- PR создаётся только автоматически
- Человек не копирует код вручную

### STOP-Guard
- 2 попытки без прогресса → STOP
- Требуется новый вход
- Попытки считаются по problem fingerprint

## Обязательные гейты
### Syntax
- actionlint
- shellcheck
- (опц.) yamllint

### Policy
- allowlist путей
- лимит файлов
- лимит LOC

### Semantic (PR body)
INTENT:
- Fixes:
- Must NOT change:

GLOBAL_IMPACT:
- affects:
- unaffected:

## Детерминизм
- вход нормализуется
- digest считается только по нормализованным данным
- QA читает только applied tree

## Last Green
- machine-truth файл: .last_green
- PR обязан базироваться на нём
- обновляется только вручную

## Guard Zones
Следующие зоны read-only для AI:
- CI guards
- policy
- fingerprint
- constitution / invariants

## Цели
### Goal Lock
- цель фиксируется в начале
- изменение цели = новая задача

### Terminal Failure
Допустимое состояние:
STATUS: TERMINAL_FAILURE
→ автопилот запрещён

## Режимы
- MODE: exploration
- MODE: delivery

## Promotion в main
- двухфазный:
  1) auto request
  2) human decision

## Приоритет цели
Если guard мешает зафиксированной цели —
допускается временное исключение с постмортемом.

## Complexity Budget
Каждый guard обязан:
- объяснять, что предотвращает
- иметь условие удаления

## Manual Escape Hatch
Описан в RUNBOOK.md
Используется только при сбое CI

## Роль человека
Human проверяет только:
- diff
- intent ↔ diff
- зелёные гейты

Принцип:
Автопилот уменьшает шум.
Он не заменяет мышление.
