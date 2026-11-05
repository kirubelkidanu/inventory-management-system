import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://kllunchfkzwhpiwhklzz.supabase.co'
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'sb_publishable_08sHZvm3HnDFO8hwh5mRog_Rbk_Z33Q'

if (!import.meta.env.VITE_SUPABASE_URL) {
  console.warn(
    '[Supabase Config Warning] VITE_SUPABASE_URL is empty or not configured in environment variables. Falling back to configured project endpoint.'
  )
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
