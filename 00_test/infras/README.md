# Infrastructure Tests

Kiểm tra xem các infrastructure services đã được setup đúng chưa.

## Prerequisites

1. **Start Docker services:**

```bash
# Từ thư mục gốc OCR
docker-compose -f docker-compose.infra.yml up -d
```

2. **Wait for services to be healthy:**

```bash
docker-compose -f docker-compose.infra.yml ps
```

3. **Install test dependencies:**

```bash
cd 00_test/infras
pip install -r requirements.txt
```

## Run Tests

### Run all tests:

```bash
python run_all.py
```

### Run individual tests:

```bash
# Test MinIO (Object Storage)
python test_minio.py

# Test NATS (Message Queue)
python test_nats.py

# Test SQLite (Database)
python test_sqlite.py
```

## Expected Output

```
============================================================
OCR Platform - Infrastructure Tests
============================================================

Running MinIO tests...
  ✓ Connection
  ✓ Create Buckets
  ✓ Upload/Download
  ✓ Presigned URL

Running NATS tests...
  ✓ Connection
  ✓ JetStream Enabled
  ✓ Create Streams
  ✓ Publish/Consume
  ✓ HTTP Monitoring

Running SQLite tests...
  ✓ Connection
  ✓ WAL Mode
  ✓ Create Table
  ✓ CRUD Operations
  ✓ Cleanup

============================================================
FINAL SUMMARY
============================================================
  ✓ PASS: MinIO
  ✓ PASS: NATS
  ✓ PASS: SQLite

🎉 All infrastructure tests passed!
```

## Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| MinIO API | http://localhost:9000 | S3-compatible API |
| MinIO Console | http://localhost:9001 | Web UI (admin/minioadmin) |
| NATS Client | nats://localhost:4222 | Client connections |
| NATS Monitoring | http://localhost:8222 | HTTP monitoring |
| SQLite | ./data/ocr_platform.db | Local database file |

## Troubleshooting

### MinIO không connect được:
```bash
# Check container
docker logs ocr-minio

# Restart
docker-compose -f docker-compose.infra.yml restart minio
```

### NATS JetStream không hoạt động:
```bash
# Check container
docker logs ocr-nats

# Verify JetStream
curl http://localhost:8222/jsz
```

### SQLite permission error:
```bash
# Ensure data directory exists
mkdir -p data
chmod 755 data
```
