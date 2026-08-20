/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 默认 `/api`；与后端不同域时填完整前缀，如 `http://127.0.0.1:8080/api` */
  readonly VITE_API_BASE: string;
  /** SSE 根地址，默认空表示当前页面同源（开发时经 Vite 代理）；分域时填 `http://127.0.0.1:8080` */
  readonly VITE_SSE_BASE: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
