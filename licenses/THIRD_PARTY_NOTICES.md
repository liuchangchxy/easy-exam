# Third-Party Notices and Licenses

This project includes code derived or adapted from the following open-source software:

## 1. Exameow

- **Source**: https://github.com/heshengtao/exameow (commit `70e0d70`)
- **License**: Apache License, Version 2.0 (see [APACHE-2.0.txt](APACHE-2.0.txt))
- **Copyright**: Copyright (c) Exameow contributors
- **Adapted Files**:
  - `backend/app/infrastructure/importers/spreadsheet_importer.py`
    (Adapted column mapping, delimiter detection, prefix stripping, and difficulty normalization from `frontend/src/utils/importParser.ts`)

## 2. EXAM-MASTER

- **Source**: https://github.com/CiE-XinYuChen/EXAM-MASTER (commit `b7e59fe`)
- **License**: MIT License
- **Copyright**: Copyright (c) CiE-XinYuChen
- **Referenced Architecture**:
  - `backend/app/infrastructure/db/repositories/question_repository.py`
  - `backend/app/application/import_service.py`
  - `tests/test_v1_import.py`
    (Transactional single-batch rollback and test scenario pattern referenced from `db.py` and `tests/test_app.py`)

## 3. MiaowTest

- **Source**: https://github.com/qijun1900/miaowtest (commit `803dadcf14a9bcb5e62deba237e15e90641a9d5a`)
- **License**: MIT License (see [MIT-MIAOWTEST.txt](MIT-MIAOWTEST.txt))
- **Copyright**: Copyright (c) 2026 qijun1900
- **Adapted Files**:
  - `backend/app/infrastructure/db/repositories/ai_conversation_repository.py`
    (Adapted conversation and message identity, sequential sequence ordering, parent message tree branching from `Express-node/models/AgentMessageModel.js` and `AgentConversationModel.js`)
  - `backend/app/infrastructure/db/connection.py`
    (Migration 13 schema for `ai_conversations` and `ai_messages`)

## 4. OpenTutor

- **Source**: https://github.com/zijinz456/OpenTutor (commit `4f169f5`)
- **License**: MIT License (see [MIT-OPENTUTOR.txt](MIT-OPENTUTOR.txt))
- **Copyright**: Copyright (c) 2026 Zijin Zhang
- **Adapted Files**:
  - `backend/legacy/services/fsrs.py`
    (Adapted FSRS-5 21-parameter scheduling formulas, initial stability and difficulty, damping update, retrievability curve, and intra-day stability calculation from `apps/api/services/spaced_repetition/fsrs.py`)

