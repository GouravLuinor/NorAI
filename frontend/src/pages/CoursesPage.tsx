import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  BookOpen,
  Plus,
  Trash2,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  FolderPlus,
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { FOCUS_RING } from '../components/ui/shared'
import { useAuthStore } from '../stores/useAuthStore'
import { useCourseStore } from '../stores/useCourseStore'
import { useLectureStore } from '../stores/useLectureStore'
import type { CourseDetail, CourseLectureEntry } from '../types'

const STATUS_LABEL: Record<string, string> = {
  completed: 'Ready',
  processing: 'Processing',
  queued: 'Queued',
  failed: 'Failed',
  cancelled: 'Cancelled',
}

export function CoursesPage() {
  const navigate = useNavigate()
  const { user, openAuthModal } = useAuthStore()
  const { courses, loadCourses, createCourse, deleteCourse, fetchCourse, addLecture, removeLecture } =
    useCourseStore()
  const { lectures, loadLectures } = useLectureStore()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<CourseDetail | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (user) {
      loadCourses()
      loadLectures()
    }
  }, [user, loadCourses, loadLectures])

  const openCourse = useCallback(
    async (courseId: string) => {
      if (expandedId === courseId) {
        setExpandedId(null)
        setDetail(null)
        return
      }
      setExpandedId(courseId)
      const d = await fetchCourse(courseId)
      setDetail(d)
    },
    [expandedId, fetchCourse],
  )

  const handleCreate = async () => {
    const trimmed = name.trim()
    if (!trimmed) return
    setBusy(true)
    setError(null)
    const created = await createCourse(trimmed, description.trim() || undefined)
    setBusy(false)
    if (!created) {
      setError('Could not create course. Try again.')
      return
    }
    setName('')
    setDescription('')
    await loadCourses()
  }

  const handleDelete = async (courseId: string) => {
    if (!window.confirm('Delete this course? Its lectures are kept, only the collection goes away.')) return
    await deleteCourse(courseId)
    if (expandedId === courseId) {
      setExpandedId(null)
      setDetail(null)
    }
  }

  const handleAddLecture = async (courseId: string, lectureId: string) => {
    await addLecture(courseId, lectureId)
    setDetail(await fetchCourse(courseId))
  }

  const handleRemoveLecture = async (courseId: string, lectureId: string) => {
    await removeLecture(courseId, lectureId)
    setDetail(await fetchCourse(courseId))
  }

  if (!user) {
    return (
      <div id="main" className="min-h-screen bg-nb bg-blueprint-grid noise flex flex-col items-center justify-center px-6 py-16">
        <div className="max-w-md w-full text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-npb border border-npbr text-npt font-mono text-11 font-medium mb-6">
            <BookOpen size={12} className="text-np" />
            <span>COURSES</span>
          </div>
          <h1 className="text-28 font-bold font-serif text-nt tracking-tight mb-3">Sign in to see your courses</h1>
          <p className="text-13 text-nt2 mb-6">Group your lectures into courses and keep related material together.</p>
          <div className="flex justify-center gap-3">
            <Button variant="primary" className="px-5 py-2 rounded-md text-12 gap-2" onClick={() => openAuthModal('login')}>
              Log in
            </Button>
            <Button variant="outline" className="px-5 py-2 rounded-md text-12 gap-2 bg-transparent border-bdr2 hover:border-nt4" onClick={() => openAuthModal('signup')}>
              Create account
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div id="main" className="min-h-screen bg-nb bg-blueprint-grid noise flex flex-col items-center py-12 px-6">
      <div className="w-full max-w-3xl flex flex-col gap-6 relative z-10">
        <button
          onClick={() => navigate('/workspace')}
          className="inline-flex items-center gap-1.5 text-12 text-nt3 hover:text-nt self-start cursor-pointer"
        >
          <ArrowLeft size={14} /> Back to workspace
        </button>

        <div className="text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-npb border border-npbr text-npt font-mono text-11 font-medium mb-4">
            <BookOpen size={12} className="text-np" />
            <span>COURSES</span>
          </div>
          <h1 className="text-32 font-bold font-serif text-nt tracking-tight mb-2 text-balance">
            Your courses
          </h1>
          <p className="text-14 text-nt2 max-w-xl mx-auto">
            Organize lectures into collections. A lecture can belong to several courses.
          </p>
        </div>

        {/* Create course */}
        <section className="rounded-lg bg-ns border border-bdr p-4">
          <form
            className="flex flex-col gap-3 sm:flex-row sm:items-center"
            onSubmit={(e) => {
              e.preventDefault()
              handleCreate()
            }}
          >
            <input
              aria-label="Course name"
              className={`flex-1 rounded-md bg-ns2 border border-bdr2 px-3 py-2 text-13 text-nt placeholder:text-nt4 outline-none ${FOCUS_RING}`}
              placeholder="Course name (e.g. Intro to CS)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={256}
            />
            <input
              aria-label="Course description"
              className="flex-1 rounded-md bg-ns2 border border-bdr2 px-3 py-2 text-13 text-nt placeholder:text-nt4 outline-none sm:max-w-60"
              placeholder="Description (optional)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={512}
            />
            <Button
              variant="primary"
              type="submit"
              disabled={!name.trim() || busy}
              className="px-4 py-2 rounded-md text-12 gap-1.5"
            >
              <Plus size={14} /> Create
            </Button>
          </form>
          {error && <p className="mt-2 text-11 text-nr">{error}</p>}
        </section>

        {/* Course list */}
        <section className="flex flex-col gap-3">
          {courses.length === 0 ? (
            <p className="text-center text-12 text-nt3 py-10">
              No courses yet — create one above, or from the upload page.
            </p>
          ) : (
            courses.map((c) => (
              <div key={c.course_id} className="rounded-lg bg-ns border border-bdr overflow-hidden">
                <div className="flex items-center gap-3 p-4">
                  <button
                    onClick={() => openCourse(c.course_id)}
                    aria-expanded={expandedId === c.course_id}
                    className={`flex-1 flex items-center gap-3 text-left cursor-pointer ${FOCUS_RING} rounded-md`}
                  >
                    {expandedId === c.course_id ? (
                      <ChevronDown size={16} className="text-nt4 shrink-0" />
                    ) : (
                      <ChevronRight size={16} className="text-nt4 shrink-0" />
                    )}
                    <span className="text-14 font-medium text-nt truncate">{c.name}</span>
                    {c.description && <span className="text-11 text-nt3 truncate hidden sm:block">{c.description}</span>}
                  </button>
                  <span className="text-11 text-nt3 tabular-nums shrink-0">
                    {c.lecture_count} lecture{c.lecture_count === 1 ? '' : 's'}
                  </span>
                  <Button
                    variant="ghost"
                    aria-label={`Delete ${c.name}`}
                    className="p-1.5 rounded-md text-nt4 hover:text-nr"
                    onClick={() => handleDelete(c.course_id)}
                  >
                    <Trash2 size={14} />
                  </Button>
                </div>

                {expandedId === c.course_id && (
                  <div className="border-t border-bdr p-4 flex flex-col gap-4">
                    {/* Add from library */}
                    <div className="flex flex-col gap-2">
                      <p className="text-11 text-nt3 font-medium flex items-center gap-1.5">
                        <FolderPlus size={12} /> Add from your lectures
                      </p>
                      {lectures.length === 0 ? (
                        <p className="text-11 text-nt4">No lectures yet — upload one first.</p>
                      ) : (
                        <div className="flex flex-wrap gap-2">
                          {lectures.map((l) => {
                            const already = detail?.lectures.some((m) => m.lecture_id === l.lecture_id)
                            return (
                              <Button
                                key={l.lecture_id}
                                variant="outline"
                                disabled={already}
                                className="px-2.5 py-1 rounded-md text-11 bg-transparent border-bdr2"
                                onClick={() => handleAddLecture(c.course_id, l.lecture_id)}
                              >
                                {already ? 'Added' : `+ ${l.title}`}
                              </Button>
                            )
                          })}
                        </div>
                      )}
                    </div>

                    {/* Members */}
                    <div className="flex flex-col gap-2">
                      <p className="text-11 text-nt3 font-medium">Lectures in this course</p>
                      {!detail || detail.lectures.length === 0 ? (
                        <p className="text-11 text-nt4">This course has no lectures yet.</p>
                      ) : (
                        detail.lectures.map((lec: CourseLectureEntry) => (
                          <div key={lec.lecture_id} className="flex items-center gap-3 rounded-md border border-bdr2 bg-ns2 px-3 py-2">
                            <button
                              onClick={() => navigate(`/workspace/${lec.lecture_id}`)}
                              className="flex-1 flex items-center gap-2 text-left text-12 text-nt2 hover:text-nt cursor-pointer"
                            >
                              <span className="truncate">{lec.title}</span>
                              <span className="text-10 text-nt4 shrink-0 font-mono">{STATUS_LABEL[lec.status] ?? lec.status}</span>
                            </button>
                            <button
                              aria-label={`Open ${lec.title}`}
                              className="p-1 text-nt4 hover:text-nt cursor-pointer"
                              onClick={() => navigate(`/workspace/${lec.lecture_id}`)}
                            >
                              <ExternalLink size={13} />
                            </button>
                            <button
                              aria-label={`Remove ${lec.title} from course`}
                              className="p-1 text-nt4 hover:text-nr cursor-pointer"
                              onClick={() => handleRemoveLecture(c.course_id, lec.lecture_id)}
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </section>
      </div>
    </div>
  )
}