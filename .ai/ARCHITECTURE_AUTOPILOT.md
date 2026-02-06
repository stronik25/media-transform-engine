# Media Transformation Engine — AUTOPILOT v1 (Invariant Snapshot)

Дата фиксации: 2026-02-06  
Статус: STABLE / IN PRODUCTION

---

## 0. Назначение документа

Этот файл фиксирует **архитектуру, инварианты и запреты** автопилота.
Любые изменения CI/CD, LLM-пайплайна или Apply-процесса
**НЕ ДОЛЖНЫ нарушать пункты ниже**, если не указано явно и осознанно.

Цель автопилота:
- автоматическое применение LLM-изменений
- с максимальной безопасностью
- без ручных кликов
- без прямых записей в `main`

---

## 1. Общая архитектура (high-level)

### Основные workflow:

1. **AI Debug**
   - источник изменений
   - генерирует deterministic и LIVE артефакты
   - может запросить `apply_live=true`
   - НИКОГДА не пишет в `main`

2. **AUTO Apply**
   - слушает завершение AI Debug (`workflow_run`)
   - сам решает, запускать Apply или нет
   - имеет kill-switch
   - не делает изменений сам

3. **Apply LIVE DEV**
   - единственный workflow, который применяет изменения
   - работает ТОЛЬКО из artifact
   - создаёт PR
   - включает auto-merge
   - удаляет ветку после мержа

---

## 2. Ключевые инварианты (ЛОМАТЬ НЕЛЬЗЯ)

### Git / PR модель
- ❌ Никаких прямых записей в `main`
- ✅ Все изменения — **ТОЛЬКО через PR**
- ✅ Apply создаёт отдельную ветку `ai-live/issue-N`
- ✅ Используется squash merge
- ✅ Ветка удаляется после мержа

### Artifact-first модель
- ✅ Apply читает **ТОЛЬКО artifact**
- ❌ Apply не читает `main` как источник данных
- ❌ QA не читает `main`
- ✅ Всё, что применяется — приходит из `live-dev` artifact

### LLM ограничения
- ❌ LLM никогда не пишет в `main`
- ❌ LLM не управляет git напрямую
- ✅ LLM работает только внутри AI Debug

---

## 3. AUTO Apply — правила

### Trigger
- AUTO запускается ТОЛЬКО после успешного AI Debug
- AUTO проверяет флаг `apply_live=true` в `preflight summary`

### Kill-switch
- Управляется repo variable:
AUTO_APPLY_ENABLED=true|false

- Если `false` или не задана → автопилот остановлен (green exit)

### Запуск Apply
- Apply запускается **по имени workflow**, не по имени файла:
Apply LIVE DEV (by run_id)


---

## 4. Apply LIVE DEV — правила

### Replay protection
- **Глобальный replay-guard**:
- файл `.ai/dev/applied_digests.txt`
- если digest уже применялся → green skip
- **Branch-level replay-guard**:
- защита от повторного apply в рамках одного PR

### No-diff guard
- Если после применения artifact нет diff → green skip
- PR не создаётся

### Allowlist (жёстко)
Apply может менять **ТОЛЬКО**:
- `.ai/dev/**`
- `output/apply_digest.txt`

Любые другие изменения → FAIL.

---

## 5. QA gate (artifact-applied tree only)

QA проверяет:
- наличие `.ai/dev/issue_<N>.md`
- валидность `apply_digest.txt`
- наличие digest в `.ai/dev/applied_digests.txt`
- JSON-валидность `request/response` (если присутствуют)

QA:
- ❌ не читает `main`
- ❌ не ходит в сеть
- ❌ не запускает LLM

---

## 6. Файлы состояния (contract)

### Обязательные:
- `.ai/dev/issue_<N>.md` — результат DEV
- `output/apply_digest.txt` — digest контракта
- `.ai/dev/.applied_ok` — маркер успешного apply
- `.ai/dev/applied_digests.txt` — глобальная защита от повторов

### Опциональные:
- `.ai/dev/request_<N>.json`
- `.ai/dev/response_<N>.json`
- `.ai/dev/digest-history.jsonl`

---

## 7. Что считается нарушением

❌ Прямой коммит в `main`  
❌ Apply без PR  
❌ Apply, читающий `main`  
❌ QA, читающий `main`  
❌ LLM, имеющий доступ к git  
❌ Изменения вне allowlist  
❌ Отключение replay-guard без явного решения  

---

## 8. Изменения архитектуры

Любое изменение:
- replay-guard
- allowlist
- AUTO / Apply связки
- модели PR/merge

должно:
1) быть явно описано
2) быть согласовано
3) обновить этот файл

---

## 9. Статус

AUTOPILOT v1:
- ✅ стабилен
- ✅ протестирован
- ✅ используется
- ✅ защищён от повторов и UX-ловушек GitHub

Следующие шаги возможны **только поверх этих инвариантов**.
