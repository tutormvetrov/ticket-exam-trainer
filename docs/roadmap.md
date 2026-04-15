# Roadmap

## Реализовано

1. Структура проекта по слоям.
2. Базовый PySide6 UI-каркас.
3. Доменные сущности карты знаний билета.
4. SQLite schema и repository.
5. Импорт `DOCX` и `PDF` в основном продукте.
6. Rule-based structuring и exercise generation.
7. Реальная установка и проверка Ollama.
8. Prompt templates и Ollama service.
9. Micro-skill scoring.
10. Adaptive repeat.
11. Cross-ticket concept linking.
12. Асинхронный import flow с progress bar и resumable хвостом.
13. Профиль `Госэкзамен` с block scores, criterion scores и отдельной статистикой.
14. 7 реальных training workspace в UI.
15. Первая рабочая DLC-вертикаль `Защита DLC`.
16. Тесты и audit standard.

## Частично реализовано

### Основной продукт

1. Windows release path подтверждён, включая menu-by-menu click-audit по всем 7 training workspace.
2. Часть polish-задач по onboarding и visual clean-up всё ещё относится к следующему циклу, но не блокирует polished Windows beta.

### DLC `Тезис`

Уже есть:

1. paywall
2. локальная активация по ключу
3. создание проектов
4. импорт материалов
5. dossier
6. outline доклада
7. storyboard слайдов
8. вопросы комиссии
9. mock defense

Остаётся недоведённым:

1. DLC пока нельзя называть завершённым коммерческим модулем
2. отдельные workflow уровня `научрук` и `оппонент` ещё не оформлены как самостоятельные пользовательские режимы
3. отдельный пользовательский режим анализа логических дыр в ответах ещё не выведен

### macOS

1. code-path, scripts и docs уже подготовлены
2. unit-level platform adaptation закрыта
3. финальный runtime smoke-run на реальном Mac остаётся открытым QA-пунктом

## Далее

1. Добавить полноценный `import preview` до старта импорта.
2. Усилить качество разбора одного большого `DOCX`.
3. Довести onboarding и пользовательскую документацию до polished release уровня при следующем крупном UI-цикле.
4. Расширить DLC до полного ранее согласованного объёма.
5. Подтвердить macOS runtime path на реальном устройстве.
