'use client';

import { useRouter, usePathname } from 'next/navigation';
import { Layout, Menu } from 'antd';
import {
  DashboardOutlined,
  FileTextOutlined,
  FolderOutlined,
  ExperimentOutlined,
} from '@ant-design/icons';

const { Sider } = Layout;


interface AppSidebarProps {
  collapsed: boolean;
  onCollapse: (collapsed: boolean) => void;
}

const AppSidebar = ({ collapsed, onCollapse }: AppSidebarProps) => {
  const router = useRouter();
  const pathname = usePathname();

  const handleMenuClick = (key: string) => {
    switch (key) {
      case 'dashboard':
        router.push('/');
        break;
      case 'models':
        router.push('/models');
        break;
      case 'data-prep':
        router.push('/dataprep');
        break;
      case 'files':
        router.push('/files');
        break;

      case 'finetuning':
        router.push('/finetuning');
        break;
      case 'team':
        router.push('/team');
        break;
      case 'settings':
        router.push('/settings');
        break;
      default:
        break;
    }
  };

  const getSelectedKey = () => {
    if (pathname === '/') return ['dashboard'];

    if (pathname.startsWith('/finetuning')) return ['finetuning'];
    if (pathname.startsWith('/models')) return ['models'];
    if (pathname.startsWith('/dataprep')) return ['data-prep'];
    if (pathname.startsWith('/files')) return ['files'];
    if (pathname.startsWith('/team')) return ['team'];
    if (pathname.startsWith('/settings')) return ['settings'];
    return ['dashboard'];
  };
  const menuItems = [
    {
      key: 'dashboard',
      icon: <DashboardOutlined />,
      label: 'Dashboard',
    },
    // {
    //   key: 'models',
    //   icon: <RobotOutlined />,
    //   label: 'Models',
    // },
    
    {
      key: 'files',
      icon: <FolderOutlined />,
      label: 'Files',
    },
    {
      key: 'data-prep',
      icon: <FileTextOutlined />,
      label: 'Data Preparation',
    },

    {
      key: 'finetuning',
      icon: <ExperimentOutlined />,
      label: 'Fine-Tuning',
    },
    // {
    //   key: 'team',
    //   icon: <TeamOutlined />,
    //   label: 'Team',
    // },
    // {
    //   key: 'settings',
    //   icon: <SettingOutlined />,
    //   label: 'Settings',
    // },
  ];

  return (
    <Sider
      collapsible
      collapsed={collapsed}
      onCollapse={onCollapse}
      width={240}
      collapsedWidth={80}
      style={{
        overflow: 'auto',
        height: 'calc(100vh - 64px)',
        position: 'fixed',
        left: 0,
        top: 64,
        zIndex: 999,
      }}
      trigger={null} // We'll add a custom trigger in the header
    >
      <Menu
        mode="inline"
        selectedKeys={getSelectedKey()}
        items={menuItems}
        inlineCollapsed={collapsed}
        onClick={({ key }) => handleMenuClick(key)}
        style={{
          borderRight: 0,
          height: '100%',
        }}
      />
    </Sider>
  );
};

export default AppSidebar;