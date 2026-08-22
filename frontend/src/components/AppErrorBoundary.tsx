import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

/** App-level boundary: a render crash anywhere shows a recovery panel instead
 * of a blank page (P5.6). Prints the error to the console for diagnosis. */
export class AppErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('App render error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-nb bg-blueprint-grid noise text-nt flex items-center justify-center px-6">
          <div className="max-w-md w-full border border-nrbr p-6 rounded-lg bg-nrb text-nr">
            <h1 className="text-lg font-semibold mb-2">Something went wrong</h1>
            <p className="text-xs text-nt3 mb-4">
              The app hit an unexpected error. Reloading usually fixes it.
            </p>
            <p className="font-mono text-xs whitespace-pre-wrap mb-5 max-h-40 overflow-auto">
              {this.state.error?.message || '(no error details)'}
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="bg-np text-npfg text-13 font-medium px-4 py-2 rounded-md"
            >
              Reload
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}