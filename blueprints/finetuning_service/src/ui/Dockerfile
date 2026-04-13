# Use the official Node.js image as base
FROM node:20-alpine AS base

# Proxy build args (set only when behind a proxy; passed via --opt=build-arg at build time)
ARG http_proxy
ARG https_proxy
ARG no_proxy
ENV http_proxy=${http_proxy} \
    https_proxy=${https_proxy} \
    no_proxy=${no_proxy}

# Build stage
FROM base AS builder
ARG http_proxy
ARG https_proxy
ARG no_proxy
ENV http_proxy=${http_proxy} \
    https_proxy=${https_proxy} \
    no_proxy=${no_proxy}
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Install dependencies using npm
COPY package.json package-lock.json ./
RUN npm ci

# Copy application code
COPY . .

# Next.js collects completely anonymous telemetry data about general usage.
# Learn more here: https://nextjs.org/telemetry
# Accept build arguments from Kaniko
ARG NEXT_PUBLIC_AUTH_URL
ARG NEXT_PUBLIC_BASE_PATH
ARG NEXT_PUBLIC_FILES_BASE_URL
ARG NEXT_PUBLIC_DATAPREP_BASE_URL
ARG NEXT_PUBLIC_FINETUNING_API_URL
ARG NEXT_TELEMETRY_DISABLED=1

ENV NEXT_PUBLIC_AUTH_URL=${NEXT_PUBLIC_AUTH_URL} \
    NEXT_PUBLIC_BASE_PATH=${NEXT_PUBLIC_BASE_PATH} \
    NEXT_PUBLIC_FILES_BASE_URL=${NEXT_PUBLIC_FILES_BASE_URL} \
    NEXT_PUBLIC_DATAPREP_BASE_URL=${NEXT_PUBLIC_DATAPREP_BASE_URL} \
    NEXT_PUBLIC_FINETUNING_API_URL=${NEXT_PUBLIC_FINETUNING_API_URL} \
    NEXT_TELEMETRY_DISABLED=${NEXT_TELEMETRY_DISABLED}

RUN npm run build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV production
ENV NEXT_TELEMETRY_DISABLED 1


RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public

# Set the correct permission for prerender cache
RUN mkdir .next && chown nextjs:nodejs .next

# Automatically leverage output traces to reduce image size
# https://nextjs.org/docs/advanced-features/output-file-tracing
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT 3000
# set hostname to localhost
ENV HOSTNAME "0.0.0.0"

# Run the application
CMD ["node", "server.js"]