function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col items-center justify-center p-8">
      <header className="text-center mb-12">
        <h1 className="text-4xl font-bold tracking-tight text-white mb-4">
          Radar de Riesgo de Corrupción
        </h1>
        <p className="text-xl text-gray-400 mb-2">Colombia</p>
        <p className="text-sm text-gray-500 max-w-xl">
          Sistema de detección de riesgo de corrupción en contratación pública colombiana,
          con dashboard web estático.
        </p>
      </header>

      <main className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 w-full max-w-4xl mb-12">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center">
          <p className="text-3xl font-bold text-green-400 mb-1">—</p>
          <p className="text-sm text-gray-400">Contratos analizados</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center">
          <p className="text-3xl font-bold text-yellow-400 mb-1">—</p>
          <p className="text-sm text-gray-400">Valor total (COP)</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center">
          <p className="text-3xl font-bold text-orange-400 mb-1">—</p>
          <p className="text-sm text-gray-400">Casos de riesgo alto</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center">
          <p className="text-3xl font-bold text-red-400 mb-1">—</p>
          <p className="text-sm text-gray-400">Casos críticos</p>
        </div>
      </main>

      <nav className="flex gap-4 text-sm text-gray-500">
        <span className="px-3 py-1 rounded bg-gray-800 text-gray-300">Panorama</span>
        <span className="px-3 py-1 rounded hover:bg-gray-800 cursor-pointer">Casos prioritarios</span>
        <span className="px-3 py-1 rounded hover:bg-gray-800 cursor-pointer">Entidades</span>
        <span className="px-3 py-1 rounded hover:bg-gray-800 cursor-pointer">Metodología</span>
      </nav>

      <footer className="mt-16 text-xs text-gray-600 text-center max-w-md">
        Los puntajes son indicadores de riesgo para priorización de auditorías,
        no acusaciones. Toda información proviene de fuentes oficiales del Estado colombiano.
      </footer>
    </div>
  )
}

export default App
