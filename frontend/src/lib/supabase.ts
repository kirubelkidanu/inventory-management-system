import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL =
  import.meta.env.VITE_SUPABASE_URL || 'https://kllunchfkzwhpiwhklzz.supabase.co'
const SUPABASE_ANON_KEY =
  import.meta.env.VITE_SUPABASE_ANON_KEY ||
  'sb_publishable_08sHZvm3HnDFO8hwh5mRog_Rbk_Z33Q'

if (!import.meta.env.VITE_SUPABASE_URL) {
  console.warn(
    '[Supabase Config Warning] VITE_SUPABASE_URL is empty or not configured in environment variables. Falling back to configured production project endpoint.'
  )
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
