import type { Metadata } from 'next'
import './globals.css'
import Navbar from '@/components/Navbar'
import Ticker from '@/components/Ticker'
import { AuthProvider } from '@/contexts/AuthContext'
import { WishlistProvider } from '@/contexts/WishlistContext'

export const metadata: Metadata = {
  title: 'MarketLens — Price Intelligence',
  description: 'Compare prices across 20+ Indian stores. Find the best deal instantly.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <WishlistProvider>
            <Ticker />
            <Navbar />
            <main>{children}</main>
          </WishlistProvider>
        </AuthProvider>
      </body>
    </html>
  )
}