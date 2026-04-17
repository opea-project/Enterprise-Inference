import React, { createContext, useContext, useReducer, useCallback, useEffect } from 'react';
import type {
  GlobalState,
  GlobalAction,
  ThemeMode,
} from '@core/types';
import { config } from '../config/appConfig';

export const initialState: GlobalState = {
  theme: {
    mode: config.defaultTheme,
  },
};

export const globalReducer = (state: GlobalState, action: GlobalAction): GlobalState => {
  switch (action.type) {
    case 'SET_THEME':
      if (typeof window !== 'undefined') {
        localStorage.setItem('theme', action.payload);
      }
      return {
        ...state,
        theme: {
          mode: action.payload,
        },
      };
    case 'TOGGLE_THEME':
      const newMode = state.theme.mode === 'dark' ? 'light' : 'dark';
      if (typeof window !== 'undefined') {
        localStorage.setItem('theme', newMode);
      }
      return {
        ...state,
        theme: {
          mode: newMode,
        },
      };
    default:
      return state;
  }
};

export const GlobalStateContext = createContext<{
  state: GlobalState;
  dispatch: React.Dispatch<GlobalAction>;
  setTheme: (mode: ThemeMode) => void;
  toggleTheme: () => void;
} | null>(null);

export function GlobalStateProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(globalReducer, initialState);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light' || savedTheme === 'dark') {
      if (savedTheme !== state.theme.mode) {
        dispatch({ type: 'SET_THEME', payload: savedTheme as ThemeMode });
      }
    } else {
      localStorage.setItem('theme', state.theme.mode);
    }
  }, [dispatch, state.theme.mode]);



  const setTheme = useCallback((mode: ThemeMode) => {
    dispatch({ type: 'SET_THEME', payload: mode });
  }, [dispatch]);

  const toggleTheme = useCallback(() => {
    dispatch({ type: 'TOGGLE_THEME' });
  }, [dispatch]);

  const contextValue = {
    state,
    dispatch,
    setTheme,
    toggleTheme,
  };

  return React.createElement(GlobalStateContext.Provider, { value: contextValue }, children);
}

export function useGlobalState() {
  const context = useContext(GlobalStateContext);
  if (!context) {
    throw new Error('useGlobalState must be used within a GlobalStateProvider');
  }
  return context;
}
