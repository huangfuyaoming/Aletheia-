import React from 'react';
import StarButton from './StarTransition.jsx';

export default function StarNavigation({ onChat, onHistory }) {
  return <nav className="star-navigation" aria-label="星空导航">
    <StarButton className="conversation-star" onClick={onChat} label="对话之星，打开全屏对话" name="对话" />
    <StarButton className="memory-star" onClick={onHistory} label="记忆之星，打开全屏历史" name="历史" orbit />
  </nav>;
}
