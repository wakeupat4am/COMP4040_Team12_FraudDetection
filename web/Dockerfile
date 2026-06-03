FROM node:22-alpine

WORKDIR /app

ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

COPY package.json tsconfig.json next-env.d.ts next.config.ts ./

RUN npm install

COPY app ./app
COPY components ./components
COPY hooks ./hooks
COPY lib ./lib
COPY tests ./tests
COPY .env.example ./.env.example

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
