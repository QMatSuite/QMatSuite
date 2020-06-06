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

public class JobManager implements Runnable {
	
	//always alive during the execution of the main program. Only used when exiting the main program
	private boolean alive;

	private JobNode currentNode;
	
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

}
