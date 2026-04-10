# Product Spec

## Назначение

Приложение предназначено для локальной подготовки к обычным экзаменам и госэкзамену на Windows.
Система не должна сводиться к хранению сплошного текста.
Базовая единица работы не билет как строка, а билет как карта знаний с атомами, навыками, упражнениями, weak areas и очередью повторения.

## Product Goals

1. Импортировать учебные материалы из `PDF` и `DOCX`.
2. Превращать текст в структурированные билеты.
3. Оценивать владение материалом по микронавыкам.
4. Строить адаптивное повторение слабых мест.
5. Использовать локальный `mistral:instruct` через Ollama как интеллектуальный переработчик и экзаменатора.
6. Масштабироваться на 270+ билетов без деградации сценария повторения.

## Core Entities

- `Exam`
- `Section`
- `SourceDocument`
- `TicketKnowledgeMap`
- `KnowledgeAtom`
- `TicketSkill`
- `ExerciseTemplate`
- `ExerciseInstance`
- `AttemptRecord`
- `TicketMasteryProfile`
- `WeakArea`
- `SpacedReviewItem`
- `CrossTicketConcept`

## Supported Training Modes

- answer skeleton
- structure reconstruction
- atom recall
- semantic cloze
- odd thesis
- oral short
- oral full
- examiner follow-up
- weak area repeat
- cross-ticket repeat

## Hard Constraints

1. Никаких облачных LLM.
2. Никаких декоративных статусов подключения.
3. Никаких немаркированных заглушек.
4. Никакой подмены реальных данных demo-данными без явной маркировки.
