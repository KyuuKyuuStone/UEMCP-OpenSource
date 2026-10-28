import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts", "src/internal.ts"],
  // DEF-1：构建用不含 paths 的配置（tsconfig.json 里的 paths 仅服务 typecheck/IDE，
  // 指向 shared 源码；若让 esbuild/dts 也走 paths，会把 shared src 打进 server 产物，
  // 改变 dist 形态——构建期仍按 workspace 依赖解析 @uemcp/shared（pnpm -r 已保证
  // shared 先构建，dist 就位）。
  tsconfig: "tsconfig.build.json",
  format: ["esm"],
  target: "node20",
  platform: "node",
  dts: true,
  clean: true,
  sourcemap: false,
  banner: {
    js: "#!/usr/bin/env node",
  },
});
