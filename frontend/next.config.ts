import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'cdn.shopify.com' },
      { protocol: 'https', hostname: 'djm0962033frr.cloudfront.net' },
      { protocol: 'https', hostname: '**.cloudfront.net' },
    ],
  },
}

export default nextConfig
