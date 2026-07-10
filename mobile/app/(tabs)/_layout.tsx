import { Tabs } from 'expo-router';
import React from 'react';
import { Text } from 'react-native';

const TabIcon = ({ label, focused }: { label: string; focused: boolean }) => (
  <Text style={{ fontSize: 10, color: focused ? '#1a73e8' : '#888', marginTop: 2 }}>
    {label}
  </Text>
);

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: '#1a73e8',
        tabBarInactiveTintColor: '#888',
        headerStyle: { backgroundColor: '#1a1a2e' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: '700' },
        tabBarStyle: { height: 60 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Dashboard',
          tabBarLabel: ({ focused }) => <TabIcon label="Dashboard" focused={focused} />,
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>📊</Text>,
        }}
      />
      <Tabs.Screen
        name="time-clock"
        options={{
          title: 'Time Clock',
          tabBarLabel: ({ focused }) => <TabIcon label="Clock" focused={focused} />,
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>⏱</Text>,
        }}
      />
      <Tabs.Screen
        name="work-orders"
        options={{
          title: 'Work Orders',
          tabBarLabel: ({ focused }) => <TabIcon label="Work Orders" focused={focused} />,
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>🔧</Text>,
        }}
      />
      <Tabs.Screen
        name="maintenance"
        options={{
          title: 'Maintenance',
          tabBarLabel: ({ focused }) => <TabIcon label="Maint" focused={focused} />,
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>🔩</Text>,
        }}
      />
      <Tabs.Screen
        name="inventory"
        options={{
          title: 'Inventory',
          tabBarLabel: ({ focused }) => <TabIcon label="Inventory" focused={focused} />,
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>📦</Text>,
        }}
      />
      <Tabs.Screen
        name="quality"
        options={{
          title: 'Quality',
          tabBarLabel: ({ focused }) => <TabIcon label="Quality" focused={focused} />,
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>🔬</Text>,
        }}
      />
      <Tabs.Screen
        name="approvals"
        options={{
          title: 'Approvals',
          tabBarLabel: ({ focused }) => <TabIcon label="Approvals" focused={focused} />,
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>✅</Text>,
        }}
      />
      <Tabs.Screen
        name="lots"
        options={{
          title: 'Lots',
          tabBarLabel: ({ focused }) => <TabIcon label="Lots" focused={focused} />,
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>🏷</Text>,
        }}
      />
      <Tabs.Screen
        name="requisitions"
        options={{
          title: 'Requisitions',
          tabBarLabel: ({ focused }) => <TabIcon label="Requests" focused={focused} />,
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>📋</Text>,
        }}
      />
      <Tabs.Screen
        name="costing"
        options={{
          title: 'Costing',
          tabBarLabel: ({ focused }) => <TabIcon label="Costing" focused={focused} />,
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>💰</Text>,
        }}
      />
    </Tabs>
  );
}
