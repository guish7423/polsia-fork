"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type MeInfo } from "@/lib/api";
import Link from "next/link";

export default function Home() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    api.get<MeInfo>("/auth/me")
      .then((me) => {
        if (me.onboarding_completed) {
          router.replace("/dashboard");
        } else {
          router.replace("/onboarding");
        }
      })
      .catch(() => {
        setChecking(false);
      });
  }, [router]);

  if (checking) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-400">Loading…</div>
      </div>
    );
  }

  // Not authenticated — show landing / demo entry
  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center p-8">
      <div className="text-center max-w-lg">
        <h1 className="text-4xl font-bold mb-4">
          Polsia <span className="text-violet-400">Fork</span>
        </h1>
        <p className="text-gray-400 mb-8">
          10 AI agents automate your company operations 24/7.
        </p>
        <div className="flex gap-3 justify-center">
          <Link
            href="/demo"
            className="px-6 py-3 bg-violet-600 hover:bg-violet-500 text-white font-semibold rounded-xl transition-all"
          >
            View Live Demo
          </Link>
          <a
            href="https://github.com/guish7423/polsia-fork"
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-3 bg-gray-800 hover:bg-gray-700 text-white font-semibold rounded-xl border border-gray-700 transition-all"
          >
            GitHub
          </a>
        </div>
      </div>
    </div>
  );
}
