// expect: no-restricted-globals
// (e) planted: a request issued outside src/shared/api/.
export const load = (): Promise<Response> => fetch('/api/health')
