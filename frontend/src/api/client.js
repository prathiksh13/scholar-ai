import axios from 'axios'
import { auth } from '../firebase'

const BACKEND_ORIGIN = import.meta.env.VITE_API_URL

const api = axios.create({
  baseURL: `${BACKEND_ORIGIN}/formatflow`,
  timeout: 120000,
})

api.interceptors.request.use(async (config) => {
  const user = auth.currentUser

  if (user) {
    const token = await user.getIdToken()
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

export async function uploadDocument(file, onProgress) {
  const form = new FormData()
  form.append('file', file)

  try {
    const { data } = await api.post('/upload', form, {
      onUploadProgress: (event) => {
        if (!onProgress) return

        const total = event.total || file.size || 1

        onProgress(
          Math.min(100, Math.round((event.loaded / total) * 100))
        )
      },
    })

    console.log('uploadDocument response:', data)

    return data
  } catch (err) {
    console.error('uploadDocument failed', err)
    throw err
  }
}

export async function getDocument(documentId) {
  const { data } = await api.get(`/documents/${documentId}`)
  return data
}

export async function getCompliance(documentId) {
  const { data } = await api.get(`/compliance/${documentId}`)
  return data
}

export async function saveEditedHtml(documentId, html) {
  const { data } = await api.patch(`/documents/${documentId}`, { html })
  return data
}

export async function saveSemanticDocument(documentId, semantic) {
  const { data } = await api.patch(
    `/documents/${documentId}/semantic`,
    { semantic }
  )

  return data
}

export async function getLatexSource(documentId) {
  const { data } = await api.get(`/documents/${documentId}/latex`)
  return data
}

export async function saveLatexSource(documentId, latex) {
  const { data } = await api.patch(
    `/documents/${documentId}/latex`,
    { latex }
  )

  return data
}

export async function compileLatexSource(documentId) {
  const { data } = await api.post(
    `/documents/${documentId}/latex/compile`
  )

  return data
}

export function compiledPdfUrl(
  documentId,
  version = Date.now()
) {
  return `${BACKEND_ORIGIN}/formatflow/documents/${documentId}/pdf?v=${version}`
}

export async function fetchCompiledPdfBlob(documentId) {
  const response = await fetch(
    compiledPdfUrl(documentId),
    {
      headers: {
        ...(auth.currentUser
          ? {
              Authorization: `Bearer ${await auth.currentUser.getIdToken()}`,
            }
          : {}),
      },
    }
  )

  if (!response.ok) {
    const message = await response.text().catch(() => '')

    throw new Error(
      message || `PDF fetch failed (${response.status})`
    )
  }

  return response.blob()
}

export function streamFormatting(
  documentId,
  format,
  handlers = {}
) {
  const controller = new AbortController()

  fetch(`${api.defaults.baseURL}/format/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      document_id: documentId,
      format,
    }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok || !res.body) {
        handlers.onError?.(
          new Error('Format stream failed')
        )
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()

      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()

        if (done) break

        buffer += decoder.decode(value, {
          stream: true,
        })

        const blocks = buffer.split('\n\n')
        buffer = blocks.pop() || ''

        for (const block of blocks) {
          const lines = block.split('\n')

          let event = 'message'
          let data = ''

          for (const line of lines) {
            if (line.startsWith('event:')) {
              event = line.slice(6).trim()
            }

            if (line.startsWith('data:')) {
              data = line.slice(5).trim()
            }
          }

          if (!data) continue

          try {
            const payload = JSON.parse(data)

            if (event === 'log') {
              handlers.onLog?.(payload)
            }

            if (event === 'preview') {
              handlers.onPreview?.(payload)
            }

            if (event === 'compliance') {
              handlers.onCompliance?.(payload)
            }

            if (event === 'complete') {
              handlers.onComplete?.(payload)
            }

            if (event === 'error') {
              handlers.onError?.(
                new Error(
                  payload.message || 'Formatting failed'
                )
              )
            }
          } catch (error) {
            handlers.onError?.(error)
          }
        }
      }
    })
    .catch((error) => {
      if (error.name !== 'AbortError') {
        handlers.onError?.(error)
      }
    })

  return () => controller.abort()
}

export function exportDocxUrl(documentId) {
  return `${BACKEND_ORIGIN}/formatflow/export/${documentId}`
}

export function exportPdfUrl(documentId) {
  return `${BACKEND_ORIGIN}/formatflow/export/${documentId}?kind=pdf`
}

async function downloadBinary(url, filename) {
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      ...(auth.currentUser
        ? {
            Authorization: `Bearer ${await auth.currentUser.getIdToken()}`,
          }
        : {}),
    },
  })

  if (!response.ok) {
    const message = await response.text().catch(() => '')

    throw new Error(
      message || `Download failed (${response.status})`
    )
  }

  const blob = await response.blob()

  const objectUrl = URL.createObjectURL(blob)

  const anchor = document.createElement('a')

  anchor.href = objectUrl
  anchor.download = filename

  document.body.appendChild(anchor)

  anchor.click()
  anchor.remove()

  URL.revokeObjectURL(objectUrl)
}

export async function downloadPdf(documentId) {
  await downloadBinary(
    exportPdfUrl(documentId),
    `formatflow_${documentId.slice(0, 8)}.pdf`
  )
}

export async function downloadDocx(documentId) {
  await downloadBinary(
    exportDocxUrl(documentId),
    `formatflow_${documentId.slice(0, 8)}.docx`
  )
}

export async function getAiSuggestions(documentId) {
  const data = await getCompliance(documentId)

  return {
    suggestions: data?.issues || [],
  }
}

export default api
