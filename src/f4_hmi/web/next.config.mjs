// Next.js 설정 — Next 15 · Node 18.19 그대로 · 정적 내보내기(out/)
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',             // 완성된 웹 파일 묶음(out/)으로 뽑는다 → hmi_bridge(FastAPI)가 그대로 보여준다. Node 서버를 따로 띄우지 않는다
  images: { unoptimized: true }, // 정적 내보내기에서는 이미지 최적화 서버가 없다
};

export default nextConfig;
