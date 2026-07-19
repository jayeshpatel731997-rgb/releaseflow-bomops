import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import App from './App'
import { expect, test, vi } from 'vitest'
globalThis.fetch = vi.fn(async (input:RequestInfo|URL) => { const url=String(input); if(url.endsWith('/users'))return new Response(JSON.stringify([])); if(url.includes('/kpis'))return new Response(JSON.stringify({median_release_cycle_hours:14.2})); return new Response(JSON.stringify({items:[],page:1,page_size:25,total:0})) }) as typeof fetch
test('renders the operational release queue',async()=>{render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/queue']}><App/></MemoryRouter></QueryClientProvider>);expect(await screen.findByText('Cases requiring operational control')).toBeInTheDocument();expect(screen.getByText('Median packet → ERP-ready')).toBeInTheDocument()})
