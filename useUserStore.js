import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const createUserId = () => `student-${Math.random().toString(36).slice(2, 8)}`

export const WELLNESS_MISSIONS = [
  {
    id: 'breathing',
    title: 'Breathing Grove',
    shortTitle: 'Breathe',
    description: 'Follow a calm breathing rhythm for one minute.',
    prompt: 'Stand inside the glowing grove. Inhale for 4, hold for 2, exhale for 6.',
    points: 40,
    color: '#38bdf8',
  },
  {
    id: 'gratitude',
    title: 'Gratitude Spring',
    shortTitle: 'Gratitude',
    description: 'Name one thing that felt okay today.',
    prompt: 'Think of one small thing you appreciate, even if the day was messy.',
    points: 35,
    color: '#fbbf24',
  },
  {
    id: 'grounding',
    title: 'Grounding Stones',
    shortTitle: 'Ground',
    description: 'Use the 5-4-3-2-1 grounding method.',
    prompt: 'Notice 5 things you see, 4 you feel, 3 you hear, 2 you smell, and 1 slow breath.',
    points: 35,
    color: '#34d399',
  },
  {
    id: 'planner',
    title: 'Tiny Plan Bridge',
    shortTitle: 'Plan',
    description: 'Choose one tiny next step for your day.',
    prompt: 'Pick one task so small it feels possible, then let that be enough for now.',
    points: 45,
    color: '#c084fc',
  },
]

const initialAvatar = {
  color: '#8b5cf6',
  skin: 'oasis',
  accessory: 'trail',
  trailColor: '#a855f7',
}

export const useUserStore = create(
  persist(
    (set, get) => ({
      userId: createUserId(),
      displayName: 'Oasis Explorer',
      points: 100,
      streak: 0,
      level: 1,
      xp: 0,
      lastLogin: null,
      avatar: initialAvatar,
      completedMissions: {},
      activeMissionId: null,
      lastMissionResult: null,
      onlineMates: [],
      chatMessages: [],
      schoolName: 'Oasis School',
      lastPlayerPosition: { x: 0, y: 0, z: 0 },

      setActiveMission: (missionId) => set({ activeMissionId: missionId }),

      addPoints: (amount) => set((state) => {
        const newPoints = state.points + amount
        const newXp = state.xp + amount * 2
        const newLevel = Math.floor(Math.sqrt(newXp / 300)) + 1
        return { points: newPoints, xp: newXp, level: newLevel }
      }),

      updateAvatar: (newSettings) => set((state) => ({
        avatar: { ...state.avatar, ...newSettings },
      })),

      rotateSkin: () => set((state) => {
        const skins = ['oasis', 'sunrise', 'forest', 'cosmic']
        const nextSkin = skins[(skins.indexOf(state.avatar.skin) + 1) % skins.length]
        const colors = {
          oasis: '#8b5cf6',
          sunrise: '#f97316',
          forest: '#22c55e',
          cosmic: '#38bdf8',
        }
        return {
          avatar: {
            ...state.avatar,
            skin: nextSkin,
            color: colors[nextSkin],
            trailColor: colors[nextSkin],
          },
        }
      }),

      checkDailyReward: () => {
        const now = new Date()
        const last = get().lastLogin ? new Date(get().lastLogin) : null

        if (!last || now.toDateString() !== last.toDateString()) {
          const isStreak = last && now.getTime() - last.getTime() < 48 * 60 * 60 * 1000
          set((state) => ({
            streak: isStreak ? state.streak + 1 : 1,
            lastLogin: now.toISOString(),
            points: state.points + (isStreak ? 50 : 20),
          }))
          return true
        }
        return false
      },

      syncProfile: async () => {
        const state = get()
        try {
          const response = await fetch('/api/game/profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              user_id: state.userId,
              display_name: state.displayName,
              avatar_color: state.avatar.color,
              skin: state.avatar.skin,
            }),
          })
          if (!response.ok) return
          const data = await response.json()
          set({
            points: data.points ?? state.points,
            xp: data.xp ?? state.xp,
            level: data.level ?? state.level,
            streak: data.streak ?? state.streak,
          })
        } catch (error) {
          console.warn('Oasis profile sync failed:', error)
        }
      },

      completeMission: async (missionId, note = '') => {
        const mission = WELLNESS_MISSIONS.find((item) => item.id === missionId)
        if (!mission) return

        const state = get()
        set((current) => ({
          completedMissions: {
            ...current.completedMissions,
            [missionId]: {
              completedAt: new Date().toISOString(),
              count: (current.completedMissions[missionId]?.count || 0) + 1,
            },
          },
          lastMissionResult: mission,
        }))
        get().addPoints(mission.points)

        try {
          const response = await fetch('/api/game/progress', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              user_id: state.userId,
              display_name: state.displayName,
              avatar_color: state.avatar.color,
              skin: state.avatar.skin,
              mission_id: mission.id,
              mission_title: mission.title,
              points: mission.points,
              note,
            }),
          })
          if (response.ok) {
            const data = await response.json()
            if (data.profile) {
              set({
                points: data.profile.points,
                xp: data.profile.xp,
                level: data.profile.level,
                streak: data.profile.streak,
              })
            }
          }
        } catch (error) {
          console.warn('Oasis mission sync failed:', error)
        }
      },

      updatePlayerPosition: (position) => set({ lastPlayerPosition: position }),

      sendPresence: async () => {
        const state = get()
        try {
          const response = await fetch(`/api/game/presence?user_id=${encodeURIComponent(state.userId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              user_id: state.userId,
              display_name: state.displayName,
              avatar_color: state.avatar.color,
              skin: state.avatar.skin,
              level: state.level,
              position: state.lastPlayerPosition,
            }),
          })
          if (!response.ok) return
          const data = await response.json()
          
          set({ onlineMates: data.online || [] })
          
          if (data.messages && data.messages.length > 0) {
            set((state) => {
              const newMsgs = data.messages.filter(m => !state.chatMessages.find(existing => existing.id === m.id))
              if (newMsgs.length === 0) return state
              return { chatMessages: [...state.chatMessages, ...newMsgs].slice(-50) }
            })
          }
        } catch (error) {
          console.warn('Oasis presence sync failed:', error)
        }
      },

      sendMessage: async (text) => {
        const state = get()
        if (!text.trim()) return

        const tempId = `temp-${Date.now()}`
        const newMessage = {
          id: tempId,
          message: text,
          sender_id: 'You',
          created_at: new Date().toISOString()
        }
        
        set((state) => ({
          chatMessages: [...state.chatMessages, newMessage].slice(-50)
        }))

        try {
          const response = await fetch('/api/game/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              user_id: state.userId,
              message: text,
              position: state.lastPlayerPosition
            }),
          })
          if (!response.ok) throw new Error('Failed to send')
        } catch (error) {
          console.warn('Oasis chat send failed:', error)
        }
      },
    }),
    {
      name: 'oasis-user-storage',
      partialize: (state) => ({
        userId: state.userId,
        displayName: state.displayName,
        points: state.points,
        streak: state.streak,
        level: state.level,
        xp: state.xp,
        lastLogin: state.lastLogin,
        avatar: state.avatar,
        completedMissions: state.completedMissions,
      }),
    },
  ),
)
