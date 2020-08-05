/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package job;

import java.util.LinkedList;
import java.util.Queue;
import com.error.ShowAlert;
import com.programconst.DefaultFileNames.SettingKeys;

import javafx.scene.control.Alert.AlertType;
import project.ProjectManager;

public class JobManager implements Runnable {
	
	//always alive during the execution of the main program. Only used when exiting the main program
	private boolean alive;
	private static boolean boolParallel;
	private static int ompNumThreads=1;
	private static int mpirunNum=1;
	public static final int numCPUs = Runtime.getRuntime().availableProcessors();

	private JobNode currentNode;
	
	static {
		String ompNumStr = ProjectManager.readGlobalSettings(SettingKeys.ompNumThreads.toString());
		//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", ompNumStr);
		try {
			int ompNum = Integer.valueOf(ompNumStr);
			if(ompNum>0) {setOmpNumThreads(ompNum,false);}
			else {setOmpNumThreads(1);}
		}catch(Exception e) {
			setOmpNumThreads(1);
		}
		
		String mpiNumStr = ProjectManager.readGlobalSettings(SettingKeys.mpirunNumCores.toString());
		try {
			int mpiNum = Integer.valueOf(mpiNumStr);
			
			if(mpiNum>0) {setMpirunNum(mpiNum,false);}
			else {setMpirunNum(1);}
		}catch(Exception e) {
			setMpirunNum(1);
		}
		
		boolParallel = false;
	}
	
    private Queue<JobNode> nodeList;
    
    public JobManager() {
    	alive = true;
        currentNode = null;
        nodeList = new LinkedList<JobNode>();
        
        Thread thread = new Thread(this);
        thread.start();
	}
    
    private synchronized boolean isAlive() {
        return alive;
    }
    public synchronized void setAlive(boolean bl) {
        alive = bl;
    }
    
	@Override
	public void run() {
		while(isAlive()) {
			synchronized (this) {
                while (this.alive) {//since in synchronized block, safe to directly use this.alive field
                    this.currentNode = this.nodeList.poll();
                    if (this.currentNode != null) {break;}//if currentNode is not null, break and run it

                    try {
                        this.wait();//if there is no available job, wait until notify
                    } catch (InterruptedException e) {
                    	//if notified, catches here. Will then go back to "while loop" again
                        e.printStackTrace();
                    }
                }
            }

            if (this.currentNode != null && isAlive()) {
            	
                this.currentNode.run();
                
                synchronized (this) {//this will only execute AFTER the run FINISHED
                    this.currentNode = null;
                }
            }
        }
	}
	public synchronized void stopCurrent() {
		if (this.currentNode != null) {
            this.currentNode.stop();
        }
		this.notifyAll();
	}
	public synchronized void stopAll() {
		if (this.currentNode != null) {
            this.currentNode.stop();
        }
		this.nodeList.clear();
		this.notifyAll();
	}
	public synchronized void stop() {
        this.alive = false;

        if (this.currentNode != null) {
            this.currentNode.stop();
        }

        this.notifyAll();
    }
	public synchronized boolean addNode(JobNode node) {
		if (node != null) {
		    boolean status = this.nodeList.offer(node);
		
		    if (status) {this.notifyAll();}
		
		    return status;
		}
		return false;
	}

	public synchronized String getCurrentJobName() {
		if(this.currentNode!=null) {
		return this.currentNode.getName();}
		else {return null;}
	}

	public static int getOmpNumThreads() {
		return ompNumThreads;
	}
	public static void setOmpNumThreads(int omp) {
		setOmpNumThreads(omp, true);
	}
	private static void setOmpNumThreads(int omp, boolean boolWrite) {
		if(omp>0) {
			JobManager.ompNumThreads = omp;
			if(boolWrite) {
				ProjectManager.writeGlobalSettings(SettingKeys.ompNumThreads.toString(), Integer.toString(omp));
			}
		}
		else {
			ShowAlert.showAlert(AlertType.ERROR, "Error", "OpenMP thread number must be positive (not "+omp+")");
		}
	}

	public static int getMpirunNum() {
		return mpirunNum;
	}
	public static void setMpirunNum(int mpirunNumb) {
		setMpirunNum(mpirunNumb, true);
	}
	private static void setMpirunNum(int mpirunNumb, boolean boolWrite) {
		//ShowAlert.showAlert(AlertType.ERROR, "Debug", "mpirun number must be positive (not "+mpirunNum+")");
		if(mpirunNumb>0) {
			JobManager.mpirunNum = mpirunNumb;
			if(boolWrite) {
				ProjectManager.writeGlobalSettings(SettingKeys.mpirunNumCores.toString(), Integer.toString(mpirunNumb));
			}
		}
		else {
			ShowAlert.showAlert(AlertType.ERROR, "Error", "mpirun number must be positive (not "+mpirunNumb+")");
		}
	}

	public static boolean isBoolParallel() {
		return boolParallel;
	}

	public static void setBoolParallel(boolean bp) {
		JobManager.boolParallel = bp;
	}

}
