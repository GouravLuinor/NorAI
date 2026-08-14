import { create } from 'zustand'
import { apiGet, apiPost, apiDelete } from '../lib/http'
import type { CourseDetail, CourseSummary } from '../types'

interface CourseState {
  courses: CourseSummary[]
  loadCourses: () => Promise<void>
  createCourse: (name: string, description?: string) => Promise<CourseSummary | null>
  deleteCourse: (courseId: string) => Promise<void>
  fetchCourse: (courseId: string) => Promise<CourseDetail | null>
  addLecture: (courseId: string, lectureId: string) => Promise<void>
  removeLecture: (courseId: string, lectureId: string) => Promise<void>
}

export const useCourseStore = create<CourseState>((set) => ({
  courses: [],
  loadCourses: async () => {
    try {
      const data = await apiGet<{ courses: CourseSummary[] }>('/courses')
      set({ courses: data?.courses ?? [] })
    } catch {
      set({ courses: [] })
    }
  },
  createCourse: async (name, description) => {
    try {
      const course = await apiPost<CourseSummary>('/courses', {
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description: description ?? null }),
      })
      set((s) => ({ courses: [course, ...s.courses] }))
      return course
    } catch {
      return null
    }
  },
  deleteCourse: async (courseId) => {
    await apiDelete(`/courses/${courseId}`)
    set((s) => ({ courses: s.courses.filter((c) => c.course_id !== courseId) }))
  },
  fetchCourse: async (courseId) => {
    try {
      return await apiGet<CourseDetail>(`/courses/${courseId}`)
    } catch {
      return null
    }
  },
  addLecture: async (courseId, lectureId) => {
    await apiPost(`/courses/${courseId}/lectures`, {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lecture_id: lectureId }),
    })
  },
  removeLecture: async (courseId, lectureId) => {
    await apiDelete(`/courses/${courseId}/lectures/${lectureId}`)
  },
}))