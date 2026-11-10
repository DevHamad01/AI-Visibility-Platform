# Signal frontend

Angular standalone routes, strict TypeScript, signals, reactive forms and a shared SCSS design system.
All analytics come from the backend API. Provider secrets never enter the browser bundle.

Use Node 22.22.3 or later within Node 22 (the production Docker image uses Node 22).

```sh
npm ci
npm start
npm run build
npm run lint
npm test -- --watch=false
```

The development server runs on port 4200 and proxies `/api` to `http://localhost:8000`.
The production Dockerfile serves the compiled app with nginx and proxies `/api` to `api:8000`.
The SSE proxy disables buffering. See the root README for API, provider and Docker setup.
