# Multi-stage build for the Hawkeye demo dashboard.
# Stage 1: build the React SPA with Node.
# Stage 2: serve the static build with a tiny Node server (no nginx needed).
FROM node:20-slim AS build
WORKDIR /app
ARG VITE_DEMO_STUB
ARG VITE_API_BASE
ENV VITE_DEMO_STUB=$VITE_DEMO_STUB
ENV VITE_API_BASE=$VITE_API_BASE
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:20-slim AS runtime
WORKDIR /app
COPY --from=build /app/dist ./dist
COPY server.js ./
EXPOSE 8080
ENV PORT=8080
CMD ["node", "server.js"]
