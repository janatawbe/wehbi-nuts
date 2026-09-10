function App() {
  return (
    <div className="min-h-screen bg-stone-50 flex flex-col items-center justify-center px-6 text-center">
      <h1 className="text-4xl font-bold text-stone-900 mb-3">Wehbi Nuts</h1>
      <p className="text-stone-600 max-w-md mb-8">
        AI-powered shop digitizer and e-commerce platform, currently under
        foundation setup.
      </p>
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="rounded-lg border border-stone-200 bg-white px-6 py-4 shadow-sm">
          <p className="font-semibold text-stone-900">AI Shop Digitizer</p>
          <p className="text-sm text-stone-500">Coming in a future milestone</p>
        </div>
        <div className="rounded-lg border border-stone-200 bg-white px-6 py-4 shadow-sm">
          <p className="font-semibold text-stone-900">E-commerce Store</p>
          <p className="text-sm text-stone-500">Coming in a future milestone</p>
        </div>
      </div>
    </div>
  )
}

export default App
