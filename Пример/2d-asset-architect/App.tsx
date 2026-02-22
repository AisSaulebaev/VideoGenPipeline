import React, { useState } from 'react';
import { AssetGenerator } from './components/AssetGenerator';
import { AssetCard } from './components/AssetCard';
import { GeneratedAsset } from './types';
import { Layers, X } from 'lucide-react';

const App: React.FC = () => {
  const [assets, setAssets] = useState<GeneratedAsset[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<GeneratedAsset | null>(null);
  const [baseAsset, setBaseAsset] = useState<GeneratedAsset | null>(null);

  const handleAssetGenerated = (asset: GeneratedAsset) => {
    setAssets((prev) => [asset, ...prev]);
  };

  const handleRemix = (asset: GeneratedAsset) => {
    setBaseAsset(asset);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-slate-950 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-slate-950 to-slate-950 text-slate-100">
      
      {/* Header */}
      <header className="border-b border-slate-800/50 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2 text-indigo-400">
            <Layers size={28} />
            <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-cyan-400">
              2D Asset Architect
            </h1>
          </div>
          <div className="text-sm text-slate-500 hidden sm:block">
            Powered by Gemini 2.5 Flash
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        
        {/* Intro */}
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">
            Create Game Assets in Seconds
          </h2>
          <p className="text-slate-400 max-w-2xl mx-auto">
            Describe the texture, sprite, or tile you need. Our AI will generate high-quality 2D assets ready for your next project. 
            Perfect for prototyping and indie development.
          </p>
        </div>

        {/* Generator */}
        <AssetGenerator 
          onAssetGenerated={handleAssetGenerated} 
          baseAsset={baseAsset}
          onClearBaseAsset={() => setBaseAsset(null)}
        />

        {/* Gallery */}
        {assets.length > 0 && (
          <div className="animate-in fade-in slide-in-from-bottom-8 duration-700">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-semibold text-slate-200">Recent Generations</h3>
              <span className="text-sm text-slate-500">{assets.length} items</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
              {assets.map((asset) => (
                <AssetCard 
                  key={asset.id} 
                  asset={asset} 
                  onPreview={setSelectedAsset}
                  onRemix={handleRemix}
                />
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Fullscreen Preview Modal */}
      {selectedAsset && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
          onClick={() => setSelectedAsset(null)}
        >
          <div 
            className="relative max-w-4xl w-full bg-slate-900 rounded-2xl overflow-hidden shadow-2xl border border-slate-800 animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-slate-800">
              <h3 className="font-semibold text-lg">{selectedAsset.style} Asset</h3>
              <button 
                onClick={() => setSelectedAsset(null)}
                className="p-2 hover:bg-slate-800 rounded-full transition-colors text-slate-400 hover:text-white"
              >
                <X size={24} />
              </button>
            </div>
            
            <div className="p-8 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] bg-slate-950 flex justify-center items-center min-h-[400px]">
              <img 
                src={selectedAsset.imageUrl} 
                alt={selectedAsset.prompt} 
                className="max-w-full max-h-[70vh] rounded shadow-lg object-contain"
              />
            </div>

            <div className="p-6 bg-slate-900 border-t border-slate-800">
              <p className="text-sm text-slate-400 mb-4">Prompt used:</p>
              <div className="bg-slate-950 p-4 rounded-lg text-slate-300 font-mono text-sm border border-slate-800">
                {selectedAsset.prompt}
              </div>
              <div className="mt-4 flex justify-end gap-4">
                <button
                  onClick={() => {
                    handleRemix(selectedAsset);
                    setSelectedAsset(null);
                  }}
                  className="px-6 py-2 border border-indigo-500/50 hover:bg-indigo-500/10 text-indigo-300 hover:text-indigo-200 rounded-lg font-medium transition-colors"
                >
                  Remix This
                </button>
                <button 
                  onClick={() => {
                    const link = document.createElement('a');
                    link.href = selectedAsset.imageUrl;
                    link.download = `asset-${selectedAsset.id}.png`;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                  }}
                  className="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium transition-colors"
                >
                  Download Asset
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;