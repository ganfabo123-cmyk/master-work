import { HeadContent, Outlet, Scripts, createRootRoute } from '@tanstack/react-router'
import { AuthProvider } from '#/context/auth'
import { Navbar } from '#/components/Navbar'
import appCss from '../styles.css?url'

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: 'utf-8' },
      { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      { title: 'JobBoard — Find your next opportunity' },
      { name: 'description', content: 'Browse thousands of job listings and connect with top employers.' },
    ],
    links: [
      { rel: 'stylesheet', href: appCss },
      {
        rel: 'preconnect',
        href: 'https://fonts.googleapis.com',
      },
      {
        rel: 'stylesheet',
        href: 'https://fonts.googleapis.com/css2?family=Roboto+Flex:opsz,wght@8..144,300..700&display=swap',
      },
    ],
  }),
  shellComponent: RootDocument,
})

function RootDocument({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        <AuthProvider>
          <Navbar />
          <main style={{ minHeight: 'calc(100vh - 64px)' }}>
            {children}
          </main>
          <footer
            style={{
              background: 'var(--md-sys-color-surface-container)',
              borderTop: '1px solid var(--md-sys-color-outline-variant)',
              padding: '32px 16px',
              textAlign: 'center',
              color: 'var(--md-sys-color-on-surface-variant)',
              fontSize: 'var(--md-sys-typescale-body-medium-size)',
            }}
          >
            <p style={{ margin: 0 }}>© 2025 JobBoard. Connecting talent with opportunity.</p>
          </footer>
        </AuthProvider>
        <Scripts />
      </body>
    </html>
  )
}
