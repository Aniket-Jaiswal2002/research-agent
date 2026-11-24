# ── Build stage ───────────────────────────────────────────────────────
FROM node:20-slim AS builder

WORKDIR /app

# Copy package files first (cache optimization)
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Build the React app for production.
# The browser (not the container) calls the API, so this is the backend's published port on your machine.
# A variable set here beats frontend/.env.production in Vite.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ── Production stage ──────────────────────────────────────────────────
FROM nginx:alpine

# Copy built files to nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
