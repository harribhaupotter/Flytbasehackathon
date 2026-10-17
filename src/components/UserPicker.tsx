import React, { useState, useRef, useEffect } from 'react';
import { User, ChevronDown, Check, Shield, Wrench, HardHat, Eye } from 'lucide-react';
import { OperatorUser, OPERATOR_USERS } from '../types';

interface UserPickerProps {
  currentUser: OperatorUser;
  onSelectUser: (user: OperatorUser) => void;
}

const ROLE_ICONS: Record<string, React.ReactNode> = {
  Supervisor: <Shield className="w-3.5 h-3.5 text-blue-400" />,
  Inspector: <Eye className="w-3.5 h-3.5 text-emerald-400" />,
  Operator: <HardHat className="w-3.5 h-3.5 text-amber-400" />,
  HSE: <Wrench className="w-3.5 h-3.5 text-purple-400" />,
};

export const UserPicker: React.FC<UserPickerProps> = ({ currentUser, onSelectUser }) => {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center space-x-2 px-2.5 py-1.5 rounded-xl border border-white/[0.08] bg-white/[0.04] hover:bg-white/[0.08] transition-colors group"
        title="Switch Operator Identity"
      >
        <div className="w-5 h-5 rounded-full bg-blue-500/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
          {ROLE_ICONS[currentUser.badge] || <User className="w-3.5 h-3.5" />}
        </div>
        <div className="text-left hidden sm:block">
          <div className="text-xs font-semibold text-neutral-200 leading-none">
            {currentUser.name}
          </div>
          <div className="text-[10px] text-neutral-400 leading-tight">
            {currentUser.role}
          </div>
        </div>
        <ChevronDown className="w-3 h-3 text-neutral-400 group-hover:text-neutral-200 transition-transform" />
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-64 rounded-2xl bg-[#121218] border border-white/[0.1] shadow-2xl p-2 z-50 animate-in fade-in zoom-in-95 duration-100">
          <div className="px-2 py-1.5 text-[11px] font-semibold text-neutral-400 uppercase tracking-wider border-b border-white/[0.06] mb-1">
            Operator Persona (Identity Context)
          </div>
          <div className="space-y-1">
            {OPERATOR_USERS.map((user) => {
              const isSelected = user.id === currentUser.id;
              return (
                <button
                  key={user.id}
                  onClick={() => {
                    onSelectUser(user);
                    setOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-2.5 py-2 rounded-xl text-left transition-colors ${
                    isSelected ? 'bg-blue-600/20 border border-blue-500/30 text-white' : 'hover:bg-white/[0.06] text-neutral-300'
                  }`}
                >
                  <div className="flex items-center space-x-2.5">
                    <div className="w-7 h-7 rounded-lg bg-white/[0.05] border border-white/[0.08] flex items-center justify-center">
                      {ROLE_ICONS[user.badge] || <User className="w-3.5 h-3.5" />}
                    </div>
                    <div>
                      <div className="text-xs font-medium text-neutral-100">{user.name}</div>
                      <div className="text-[10px] text-neutral-400">{user.role} · {user.team}</div>
                    </div>
                  </div>
                  {isSelected && <Check className="w-3.5 h-3.5 text-blue-400" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
