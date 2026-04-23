# cse12-metrics

Tracks LLM token usage from ephemeral grading VMs. VMs POST one event per LLM call; a FastAPI server stores events in SQLite on a DigitalOcean VPS.

## Local Development

**Option 1: Docker (recommended)**

```bash
cp .env.example .env
# Generate a strong API key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Set API_KEY in .env with the generated key
docker-compose up
```

Access at `http://localhost:7591`

**Option 2: Direct Python**

```bash
cp .env.example .env
# Set API_KEY in .env
uv sync
uvicorn app.main:app --reload --port 7591
```

## Production Setup (DigitalOcean VPS)

```bash
cp .env.example .env
# set a strong API_KEY in .env
docker compose up -d
```

The SQLite database is stored in a named Docker volume (`db-data`). Back it up with:

```bash
docker run --rm \
  -v cse12-metrics_db-data:/data \
  -v $(pwd):/backup \
  alpine cp /data/usage.db /backup/usage.db
```

---

## API

All endpoints require the header:

```
X-API-Key: <your key>
```

### `POST /metrics/usage`

Record one LLM call from a VM.

**Body**

| Field | Type | Description |
|---|---|---|
| `name` | string | VM fleet name (e.g. `"grader"`) |
| `submission_num` | integer | Numerically increasing, unique within `name` |
| `assignment_id` | string | Assignment identifier (e.g. `"hw3"`) |
| `question_num` | integer | Question number within the assignment |
| `run_token` | string | UUID generated once at VM startup (`uuid.uuid4()`); pass the same value for all events in this grading run. The server maps it to a `grading_run` number automatically. |
| `input_tokens` | integer | Prompt tokens consumed |
| `output_tokens` | integer | Completion tokens produced |

**Example**

```bash
curl -X POST http://your-vps:7591/metrics/usage \
  -H "X-API-Key: yourkey" \
  -H "Content-Type: application/json" \
  -d '{"name":"grader","submission_num":42,"assignment_id":"hw3","question_num":1,"run_token":"f47ac10b-58cc-4372-a567-0e02b2c3d479","input_tokens":1200,"output_tokens":400}'
```

**Responses**
- `201` — recorded
- `409` — duplicate `(name, submission_num, assignment_id, question_num, grading_run)`, ignored

---

### `GET /metrics/usage/by-question`

Input/output tokens per name for a specific `assignment_id` and `question_num`, using only the latest `submission_num` and latest `grading_run` per name.

**Query params**

| Param | Type | Description |
|---|---|---|
| `assignment_id` | string | Required |
| `question_num` | integer | Required |

**Example**

```bash
curl "http://your-vps:7591/metrics/usage/by-question?assignment_id=hw3&question_num=1" \
  -H "X-API-Key: yourkey"
```

**Response**

```json
[
  {"name": "grader", "submission_num": 42, "grading_run": 2, "input_tokens": 1200, "output_tokens": 400},
  {"name": "scorer", "submission_num": 7,  "grading_run": 1, "input_tokens": 800,  "output_tokens": 300}
]
```

---

### `GET /metrics/usage/totals`

Sum of tokens across **all names**, counting only the highest `submission_num` per name. Use this to get the current total cost baseline.

**Example**

```bash
curl http://your-vps:7591/metrics/usage/totals \
  -H "X-API-Key: yourkey"
```

**Response**

```json
{"input_tokens": 84000, "output_tokens": 21000, "total_tokens": 105000}
```

---

### `GET /metrics/usage/latest-per-name`

Per-name breakdown, counting only the highest `submission_num` for each name.

**Example**

```bash
curl http://your-vps:7591/metrics/usage/latest-per-name \
  -H "X-API-Key: yourkey"
```

**Response**

```json
[
  {"name": "grader", "submission_num": 42, "input_tokens": 18400, "output_tokens": 5200, "total_tokens": 23600},
  {"name": "scorer", "submission_num": 7,  "input_tokens": 3100,  "output_tokens": 900,  "total_tokens": 4000}
]
```

---

### `GET /metrics/usage`

Raw event log. Optionally filter by `name` and/or `submission_num`.

**Query params**

| Param | Type | Description |
|---|---|---|
| `name` | string | Filter by fleet name |
| `submission_num` | integer | Filter by submission ID |
| `grading_run` | integer | Filter by grading run number |

**Examples**

```bash
# all events
curl "http://your-vps:7591/metrics/usage" -H "X-API-Key: yourkey"

# all events for a fleet
curl "http://your-vps:7591/metrics/usage?name=grader" -H "X-API-Key: yourkey"

# all events for one submission
curl "http://your-vps:7591/metrics/usage?name=grader&submission_num=42" -H "X-API-Key: yourkey"
```

**Response** — array of raw event rows, newest first:

```json
[
  {
    "event_id": 7,
    "name": "grader",
    "submission_num": 42,
    "assignment_id": "hw3",
    "question_num": 1,
    "grading_run": 1,
    "input_tokens": 1200,
    "output_tokens": 400,
    "created_at": "2026-04-22 10:14:03"
  }
]
```

---

## Client script

`client.py` queries the API from your laptop with no dependencies (stdlib only).

```bash
export METRICS_URL=http://your-vps:7591
export METRICS_API_KEY=yourkey

python client.py                                          # latest-per-name summary (default)
python client.py --assignment-id hw3 --question-num 1     # tokens per name for a specific question
python client.py --all                                    # all raw events
python client.py --name grader                            # raw events for one fleet
python client.py --name grader --submission-num 42        # single submission
```

Pass `--url` and `--key` as flags instead of env vars if preferred.
