import { useState } from 'react'
import { DigitizerPage } from './pages/DigitizerPage'
import { ReviewPage } from './pages/ReviewPage'

type View = 'digitizer' | 'review'

function App() {
  const [view, setView] = useState<View>('digitizer')

  return (
    <div className="min-h-dvh bg-cream">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <p className="font-semibold tracking-tight text-roast-800">Wehbi Nuts</p>
          <nav className="flex gap-1" aria-label="Main">
            <button
              type="button"
              onClick={() => setView('digitizer')}
              aria-current={view === 'digitizer' ? 'page' : undefined}
              className={`rounded-md px-2.5 py-1 text-sm font-medium ${
                view === 'digitizer' ? 'text-roast-800' : 'text-stone-500 hover:text-stone-800'
              }`}
            >
              Digitizer
            </button>
            <button
              type="button"
              onClick={() => setView('review')}
              aria-current={view === 'review' ? 'page' : undefined}
              className={`rounded-md px-2.5 py-1 text-sm font-medium ${
                view === 'review' ? 'text-roast-800' : 'text-stone-500 hover:text-stone-800'
              }`}
            >
              Review
            </button>
          </nav>
        </div>
      </header>
      {view === 'digitizer' ? <DigitizerPage /> : <ReviewPage />}
    </div>
  )
}

export default App
