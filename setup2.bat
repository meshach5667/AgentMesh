cd client
call npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --no-turbopack --use-npm -y
call npm install axios zustand @tanstack/react-query react-hot-toast lucide-react recharts date-fns
call npm install -D @types/node playwright @playwright/test
