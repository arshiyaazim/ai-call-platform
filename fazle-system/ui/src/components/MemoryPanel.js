"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";

const MEMORY_TYPES = ["all", "preference", "contact", "knowledge", "personal", "conversation", "image"];

export default function MemoryPanel() {
  const { data: session } = useSession();
  const [memories, setMemories] = useState([]);
  const [selectedType, setSelectedType] = useState("all");
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [previewImage, setPreviewImage] = useState(null);

  const authHeaders = () => ({
    "Content-Type": "application/json",
    ...(session?.accessToken
      ? { Authorization: `Bearer ${session.accessToken}` }
      : {}),
  });

  const fetchMemories = async () => {
    setLoading(true);
    try {
      if (selectedType === "image") {
        // Search multimodal collection for images
        const res = await fetch(`/api/fazle/memory/search-multimodal`, {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify({
            query: searchQuery || "all images",
            memory_type: "image",
            limit: 20,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          setMemories(data.results || []);
        }
      } else {
        const res = await fetch(`/api/fazle/memory/search`, {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify({
            query: searchQuery || "all memories",
            memory_type: selectedType !== "all" ? selectedType : null,
            limit: 20,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          setMemories(data.results || []);
        }
      }
    } catch {
      console.error("Failed to fetch memories");
    } finally {
      setLoading(false);
    }
  };

  const deleteMemory = async (memoryId) => {
    if (!confirm("Delete this memory?")) return;
    try {
      const res = await fetch(`/api/fazle/memory/${memoryId}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (res.ok) {
        setMemories((prev) => prev.filter((m) => m.id !== memoryId));
      }
    } catch {
      console.error("Failed to delete memory");
    }
  };

  useEffect(() => {
    fetchMemories();
  }, [selectedType]);

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-gray-800 p-4">
        <h2 className="text-lg font-semibold text-gray-200">Memory Dashboard</h2>
        <p className="text-xs text-gray-500">View and search Fazle&apos;s memories</p>
      </div>

      <div className="p-4 border-b border-gray-800 space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search memories..."
            className="flex-1 bg-[#1a1a2e] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-fazle-500"
          />
          <button
            onClick={fetchMemories}
            className="bg-fazle-600 hover:bg-fazle-700 text-white px-4 py-2 rounded-lg text-sm"
          >
            Search
          </button>
        </div>
        <div className="flex gap-2 flex-wrap">
          {MEMORY_TYPES.map((type) => (
            <button
              key={type}
              onClick={() => setSelectedType(type)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                selectedType === type
                  ? "bg-fazle-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-gray-200"
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {loading ? (
          <p className="text-gray-500 text-sm animate-pulse">Loading memories...</p>
        ) : memories.length === 0 ? (
          <p className="text-gray-500 text-sm">No memories found.</p>
        ) : selectedType === "image" ? (
          /* Thumbnail grid for images */
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {memories.map((memory, i) => (
              <div
                key={memory.id || i}
                className="bg-[#1a1a2e] border border-gray-700/50 rounded-xl overflow-hidden group cursor-pointer hover:border-fazle-500/50 transition-colors"
                onClick={() => setPreviewImage(memory.image_url || memory.thumbnail_url)}
              >
                {memory.thumbnail_url ? (
                  <img
                    src={memory.thumbnail_url}
                    alt={memory.caption || "Memory image"}
                    className="w-full h-32 object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="w-full h-32 bg-gray-800 flex items-center justify-center text-gray-500 text-2xl">
                    📷
                  </div>
                )}
                <div className="p-2">
                  <p className="text-xs text-gray-300 line-clamp-2">{memory.caption || memory.text}</p>
                  <p className="text-xs text-gray-500 mt-1">{memory.created_at?.split("T")[0]}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          memories.map((memory, i) => (
            <div
              key={memory.id || i}
              className="bg-[#1a1a2e] border border-gray-700/50 rounded-xl p-4 space-y-2 group"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-fazle-700/20 text-fazle-300">
                  {memory.type}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">{memory.created_at?.split("T")[0]}</span>
                  {memory.id && (
                    <button
                      onClick={() => deleteMemory(memory.id)}
                      className="opacity-0 group-hover:opacity-100 text-red-400/60 hover:text-red-400 text-xs transition-opacity"
                      title="Delete memory"
                    >
                      ✕
                    </button>
                  )}
                </div>
              </div>
              <p className="text-sm text-gray-200">{memory.text}</p>
              {memory.score && (
                <p className="text-xs text-gray-500">Relevance: {(memory.score * 100).toFixed(0)}%</p>
              )}
            </div>
          ))
        )}
      </div>

      {/* Image preview modal */}
      {previewImage && (
        <div
          className="fixed inset-0 z-[60] bg-black/80 flex items-center justify-center p-4 cursor-pointer"
          onClick={() => setPreviewImage(null)}
        >
          <img
            src={previewImage}
            alt="Preview"
            className="max-w-full max-h-full object-contain rounded-lg"
          />
        </div>
      )}
    </div>
  );
}
