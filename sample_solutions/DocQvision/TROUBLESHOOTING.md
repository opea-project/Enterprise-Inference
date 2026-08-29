# Troubleshooting Guide

## Common Issues

### 1. Containers Not Starting

**Symptom**: Containers fail to start or exit immediately

**Check container status:**
```bash
docker compose ps
```

**View error logs:**
```bash
docker compose logs backend
docker compose logs frontend
```

**Solution:**
```bash
# Rebuild containers
docker compose down
docker compose up -d --build
```

### 2. Backend Connection Errors

**Symptom**: Frontend shows "Failed to connect" or network errors

**Check backend health:**
```bash
curl http://localhost:5001/health
```

**Expected response:**
```json
{"status": "healthy", "auth_mode": "genai_gateway"}
```

**Solution:**
- Verify backend container is running: `docker compose ps`
- Check backend logs: `docker compose logs backend -f`
- Restart backend: `docker compose restart backend`

### 3. Authentication Errors

**Symptom**: Extraction fails with authentication errors

**Error**: `AuthenticationError` or `Invalid API key`

**Solution:**
- Check `GENAI_GATEWAY_API_KEY` in `api/.env`
- Verify API key is active and has proper permissions
- For Keycloak: Verify client secret is correct

**Error**: `Connection refused` or `Connection timeout`

**Solution:**
- Verify `GENAI_GATEWAY_URL` is correct in `api/.env`
- For Keycloak: Ensure `KEYCLOAK_BASE_URL` points to correct realm
- Test endpoint directly:
```bash
curl https://your-gateway-url.com/v1/models
```

### 4. Vision Model Errors

**Symptom**: Extraction fails at vision stage

**Error**: `Model not found` or `Model unavailable`

**Solution:**
- Verify `VISION_MODEL` is deployed and accessible
- Check model name spelling in `api/.env`
- Confirm GenAI Gateway has vision model deployed
- For Keycloak: Verify inference endpoint supports vision models

**Error**: `Rate limit exceeded` or `Quota exceeded`

**Solution:**
- Wait a few minutes and retry
- Check API usage limits with administrator
- Reduce `MAX_BATCH_UPLOAD` to process fewer files at once

### 5. PDF Upload Errors

**Symptom**: PDF upload fails or returns validation errors

**Error**: `Invalid PDF file` or `File validation failed`

**Causes:**
- Corrupted PDF file
- Password-protected PDF
- Exceeds 10MB size limit
- Exceeds 50 pages limit

**Solution:**
- Verify PDF opens in standard PDF viewer
- Remove password protection
- Compress large PDF files
- Split multi-page documents
- Check backend logs for specific error

### 6. Document Type Mismatch

**Symptom**: Extraction fails with document type validation error

**Error**: `Document type mismatch detected`

**Causes:**
- Selected wrong template for document
- Document type doesn't match template configuration
- Low confidence in document type detection

**Solution:**
- Verify correct template is selected
- Check document matches expected type (invoice, prescription, etc.)
- Upload correct document type or create new template
- For test/debugging: Use template with doc_type "test" to skip validation

### 7. Low Extraction Coverage

**Symptom**: Extraction completes but many fields are empty

**Possible causes:**
- Document quality is poor
- Fields not present in document
- Traditional extraction failed, vision model struggled
- Document layout significantly different from template

**Solution:**
- Verify document contains all expected fields
- Use high-quality, clear PDF documents
- Check if document type matches template
- Review template schema matches document structure
- Test extraction on sample document in Configure page

### 8. Frontend Not Loading

**Symptom**: Browser shows blank page or cannot connect

**Check frontend status:**
```bash
docker compose ps frontend
```

**Check frontend logs:**
```bash
docker compose logs frontend -f
```

**Solution:**
- Clear browser cache and hard refresh (Ctrl+F5)
- Verify port 3000 is not in use by another application
- Restart frontend: `docker compose restart frontend`
- Check firewall settings
- Try accessing from different browser

### 9. PDF Preview Not Working

**Symptom**: PDF preview shows error or doesn't load

**Error**: `Failed to load PDF file`

**Solution:**
- Verify PDF file is valid and not corrupted
- Check file size is under 10MB
- Ensure browser supports PDF.js
- Clear browser cache
- Check browser console for errors

### 10. Template Configuration Fails

**Symptom**: Chat-based configuration not responding or returning errors

**Error**: `Failed to process message` or `Chat response failed`

**Solution:**
- Check vision model is configured correctly
- Verify authentication is working
- Review backend logs for specific errors
- Try simpler field descriptions
- Ensure PDF is uploaded before chatting

### 11. Test Extraction Fails with 422 Error

**Symptom**: Test extraction button returns 422 error

**Error**: `Failed to test extraction: Request failed with status code 422`

**Causes:**
- Invalid schema structure
- Missing required fields in template
- Backend validation error

**Solution:**
- Check backend logs for validation details
- Ensure all fields have proper type definitions
- Restart backend: `docker compose restart backend`
- Try creating a simpler template first

### 12. Batch Upload Failures

**Symptom**: Some files in batch fail while others succeed

**Check error details:**
- Review individual file error messages in UI
- Check backend logs for specific file failures

**Common causes:**
- Individual file validation errors
- Mixed document types in batch
- One or more files corrupted
- Size or page limit exceeded on specific files

**Solution:**
- Upload failed files individually to see specific errors
- Ensure all files are same document type
- Verify each file meets requirements (size, format, pages)
- Process problem files separately

### 13. Port Already in Use

**Error**: `Port 3000 is already allocated` or `Port 5001 is already allocated`

**Find process using port:**
```bash
# Windows
netstat -ano | findstr :3000
netstat -ano | findstr :5001

# Linux/Mac
lsof -i :3000
lsof -i :5001
```

**Solution:**
- Stop the conflicting process
- Or change ports in `docker-compose.yml`

### 14. Database Errors

**Symptom**: Backend fails with database operation errors

**Error**: `Database is locked` or `OperationalError`

**Solution:**
```bash
# Stop containers
docker compose down

# Remove database volume
docker volume rm DocQvision_db_data

# Restart
docker compose up -d --build
```

**Warning**: This will delete all templates and extraction history

### 15. Out of Memory Errors

**Symptom**: Container crashes or backend becomes unresponsive

**Check logs:**
```bash
docker compose logs backend | grep -i "memory\|killed"
```

**Solution:**
- Reduce `MAX_BATCH_UPLOAD` from 5 to 2-3 files
- Process smaller PDF files
- Reduce `VISION_MAX_PAGES` from 5 to 2-3 pages
- Increase Docker memory limit in Docker Desktop settings
- Reduce `VISION_MAX_TOKENS` if using large context

### 16. CORS Errors

**Symptom**: Browser console shows CORS policy errors

**Error**: `Access to fetch has been blocked by CORS policy`

**Solution:**
- Verify backend is running on port 5001
- Check `CORS_ORIGINS` in `api/.env` includes frontend URL
- Ensure frontend is accessing correct backend URL
- Restart both containers after configuration changes

### 17. Session Lost on Refresh

**Symptom**: Template configuration session lost when page refreshes

**Explanation:**
- Configure page saves session to browser localStorage
- Data persists across page refreshes
- Intentional design for resume capability

**Solution:**
- Use "New Template" button to start fresh session
- Browser prompts to continue or start new when previous session found
- Clear browser localStorage to reset completely

### 18. Extraction Returns Incomplete Data

**Symptom**: Some fields extracted correctly, others missing

**Common causes:**
- Fields located in different sections of document
- Vision model only processed first few pages
- Field names don't match document structure

**Solution:**
- Increase `VISION_MAX_PAGES` to process more pages
- Verify field names match actual document headers
- Use more specific field descriptions in template
- Check if missing fields are on later pages

## Configuration Issues

### Invalid .env Configuration

**Symptom**: Backend fails to start with configuration errors

**Check required variables in `api/.env`:**
```bash
AUTH_MODE=genai_gateway
GENAI_GATEWAY_URL=https://your-gateway-url.com/v1
GENAI_GATEWAY_API_KEY=your-api-key-here
VISION_MODEL=Qwen/Qwen2.5-VL-7B-Instruct
```

**Common mistakes:**
- Missing required variables
- Extra spaces in variable names
- Wrong endpoint format (missing /v1)
- Quotes around values (not needed)
- Wrong AUTH_MODE value

### Authentication Mode Configuration

**For GenAI Gateway:**
```bash
AUTH_MODE=genai_gateway
GENAI_GATEWAY_URL=https://your-gateway-url.com/v1
GENAI_GATEWAY_API_KEY=your-api-key-here
VISION_MODEL=Qwen/Qwen2.5-VL-7B-Instruct
DETECTION_MODEL=Qwen/Qwen2.5-VL-7B-Instruct
```

**For Keycloak:**
```bash
AUTH_MODE=keycloak
KEYCLOAK_BASE_URL=https://your-keycloak-url.com/realms/master/protocol/openid-connect
KEYCLOAK_REALM=master
KEYCLOAK_CLIENT_ID=api
KEYCLOAK_CLIENT_SECRET=your-client-secret-here
VISION_MODEL=Qwen/Qwen2.5-VL-7B-Instruct
DETECTION_MODEL=Qwen/Qwen2.5-VL-7B-Instruct
```

## Advanced Troubleshooting

### Enable Debug Logging

Edit `api/.env`:
```bash
LOG_LEVEL=DEBUG
```

Restart backend:
```bash
docker compose restart backend
docker compose logs backend -f
```

### Test Backend Directly

**Test health endpoint:**
```bash
curl http://localhost:5001/health
```

**Test template creation:**
```bash
curl -X POST http://localhost:5001/api/templates \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Template",
    "doc_type": "test",
    "schema_json": {
      "field1": {"type": "string", "required": true},
      "field2": {"type": "number", "required": false}
    }
  }'
```

**Test document upload:**
```bash
curl -X POST http://localhost:5001/api/documents/upload \
  -F "file=@test.pdf"
```

### Inspect Container

**Access backend container shell:**
```bash
docker compose exec backend /bin/bash
```

**Check Python environment:**
```bash
docker compose exec backend pip list
docker compose exec backend python -c "import pypdf; print(pypdf.__version__)"
```

**Check database:**
```bash
docker compose exec backend python -c "
from database import engine
from sqlalchemy import inspect
inspector = inspect(engine)
print('Tables:', inspector.get_table_names())
"
```

### Clean Docker Environment

If issues persist, clean Docker completely:

```bash
# Stop and remove containers
docker compose down -v

# Remove unused images
docker system prune -a

# Rebuild from scratch
docker compose up -d --build
```

## Getting Help

If issues persist after following this guide:

1. **Collect Information:**
   - Docker logs: `docker compose logs > logs.txt`
   - Docker status: `docker compose ps`
   - Environment: `docker compose config`
   - Backend health: `curl http://localhost:5001/health`

2. **Check Configuration:**
   - Review `api/.env` file
   - Verify API keys/credentials are valid
   - Test authentication endpoint independently
   - Check vision model is deployed

3. **Try Minimal Setup:**
   - Use fresh `.env` configuration
   - Test with simple document (single page invoice)
   - Verify extraction works on known good document
   - Check if issue persists with minimal config

4. **System Information:**
   - Docker version: `docker --version`
   - Docker Compose version: `docker compose version`
   - Operating system and version
   - Available memory and disk space
