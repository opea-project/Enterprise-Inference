# Fine-Tuning UI

A comprehensive web application for managing AI model fine-tuning workflows, data preparation, and file management. Built with Next.js, TypeScript, and Ant Design.

## Features

- **Authentication & Authorization**: Secure user authentication and access control
- **File Management**: Upload, organize, and manage training datasets
- **Data Preparation**: Automated data preprocessing and preparation workflows
- **Fine-Tuning Management**: Create, monitor, and manage model fine-tuning jobs
- **Intel Hardware Support**: Optimized for Intel Xeon and Gaudi processors
- **Real-time Status Updates**: Live updates on job progress and status

## Tech Stack

- **Frontend**: Next.js 16, React 18, TypeScript
- **UI Library**: Ant Design 5.21
- **State Management**: TanStack Query (React Query)
- **Styling**: CSS Modules, PostCSS
- **Build Tool**: Next.js built-in bundler

## Environment Variables

Create a `.env.local` file in the root directory with the following variables:

```bash
# API Endpoints
NEXT_PUBLIC_AUTH_URL=http://localhost:8000
NEXT_PUBLIC_FILES_BASE_URL=http://localhost:8001
NEXT_PUBLIC_DATAPREP_BASE_URL=http://localhost:8002
NEXT_PUBLIC_FINETUNING_API_URL=http://localhost:8003

# Optional: Disable Next.js telemetry
NEXT_TELEMETRY_DISABLED=1
```

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `NEXT_PUBLIC_AUTH_URL` | Authentication service base URL | `http://localhost:8000/api/auth` |
| `NEXT_PUBLIC_FILES_BASE_URL` | File management service URL | `http://localhost:8001/api/files` |
| `NEXT_PUBLIC_DATAPREP_BASE_URL` | Data preparation service URL | `http://localhost:8002/api/dataprep` |
| `NEXT_PUBLIC_FINETUNING_API_URL` | Fine-tuning service URL | `http://localhost:8003/api/finetuning` |

## Getting Started

### Prerequisites

- Node.js 18 or higher
- npm, yarn, or pnpm

### Local Development

1. Clone the repository
2. Install dependencies:

```bash
npm install
# or
yarn install
# or
pnpm install
```

3. Create your environment file:

```bash
cp .env.example .env.local
# Edit .env.local with your configuration
```

4. Run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
```

5. Open [http://localhost:3000](http://localhost:3000) with your browser to see the application.

### Building for Production

```bash
npm run build
npm start
```

## Docker Deployment

### Building the Docker Image

```bash
# Build the Docker image
docker build -t finetuning-ui .

# Run the container
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_AUTH_URL=http://your-auth-service \
  -e NEXT_PUBLIC_FILES_BASE_URL=http://your-files-service \
  -e NEXT_PUBLIC_DATAPREP_BASE_URL=http://your-dataprep-service \
  -e NEXT_PUBLIC_FINETUNING_API_URL=http://your-finetuning-service \
  finetuning-ui
```

### Docker Compose Example

```yaml
version: '3.8'
services:
  finetuning-ui:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_AUTH_URL=http://auth-service
      - NEXT_PUBLIC_FILES_BASE_URL=http://files-service
      - NEXT_PUBLIC_DATAPREP_BASE_URL=http://dataprep-service
      - NEXT_PUBLIC_FINETUNING_API_URL=http://finetuning-service
    depends_on:
      - auth-service
      - files-service
      - dataprep-service
      - finetuning-service
```

## Project Structure

```
finetuning-ui/
├── app/                    # Next.js App Router pages
│   ├── auth/              # Authentication pages
│   ├── components/        # Shared app components
│   ├── dataprep/          # Data preparation pages
│   ├── files/             # File management pages
│   ├── finetuning/        # Fine-tuning pages
│   └── login/             # Login page
├── src/
│   ├── core/              # Core configuration and providers
│   │   ├── api/           # API configuration
│   │   ├── config/        # App configuration
│   │   ├── providers/     # React providers
│   │   └── state/         # Global state management
│   └── features/          # Feature-based modules
│       ├── auth/          # Authentication feature
│       ├── dataprep/      # Data preparation feature
│       ├── files/         # File management feature
│       └── finetuning/    # Fine-tuning feature
├── public/                # Static assets
├── Dockerfile            # Docker configuration
└── package.json          # Dependencies and scripts
```

## Available Scripts

- `npm run dev` - Starts the development server
- `npm run build` - Builds the application for production
- `npm start` - Runs the built application
- `npm run lint` - Runs ESLint for code quality
