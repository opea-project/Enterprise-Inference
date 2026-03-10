# Multi-stage build for DocuGen AI Frontend
FROM node:20-slim

# Set working directory
WORKDIR /app

# Copy package.json only
COPY package.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Expose port
EXPOSE 3000

# Set environment for Vite
ENV HOST=0.0.0.0
ENV PORT=3000
ENV VITE_API_TARGET=http://backend:5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"

# Switch to non-root user
USER appuser

# Run development server with environment variable
CMD ["sh", "-c", "VITE_API_TARGET=http://backend:5001 npm run dev -- --host 0.0.0.0 --port 3000"]
