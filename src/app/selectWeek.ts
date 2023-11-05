import { redirect } from 'next/navigation'
export async function selectWeek(formData: FormData) {
  'use server'
  const weekNum = formData.get('weekSelect')
  redirect(`/${weekNum}`);
}
