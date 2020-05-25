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
package project;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.util.ArrayList;
import java.util.LinkedHashMap;

import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumStep;

import agent.InputAgent;
import agent.InputAgentGeo;
import input.QeInput;
import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;

public class ProjectManager {
	private LinkedHashMap<String, Project> projectDict;
	private String activeProjKey;
	
	public ProjectManager() {
		projectDict = new LinkedHashMap<String, Project> ();
		activeProjKey = null;
	}
	public void saveActiveProject(File filename) {
		Project pj = getActiveProject();
		if(pj==null) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("No active project! Cannot save...");
	    	alert1.showAndWait();
			return;
		}
		
    	// Serialization 
        try { 
            // Saving of object in a file 
        	FileOutputStream file;
        	if(filename==null) {
        		file = new FileOutputStream (pj.getName()+".proj"); 
    		}
        	else {
        		file = new FileOutputStream (filename); 
        	}
            
            ObjectOutputStream out = new ObjectOutputStream (file); 
  
            // Method for serialization of object 
            out.writeObject(pj); 
  
            out.close(); 
            file.close(); 
            
            Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Success");
	    	alert1.setContentText("Successfully saved to "+filename+".");
	    	alert1.showAndWait();
        } 
  
        catch (IOException ex) { 
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("IOException is caught! Cannot save to file "+filename+"."+ex.getMessage());
	    	alert1.showAndWait();
        } 
	}
	public String loadProject(File filename) {
		Project pj;
		// Deserialization 
        try { 
            // Reading the object from a file 
            FileInputStream file = new FileInputStream (filename); 
            ObjectInputStream in = new ObjectInputStream (file); 
  
            // Method for deserialization of object 
            pj = (Project)in.readObject(); 
  
            in.close(); 
            file.close(); 
            if(pj==null) {return "Project read from file is null";}
            if(projectDict.containsKey(pj.getName())) {return "Already contains project of the same name. Please close it first before loading.";}
        	
            projectDict.put(pj.getName(), pj);
			activeProjKey = pj.getName();
			return null;
        } 
        catch (IOException ex) { 
            Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("IOException is caught! Cannot load file "+filename+"."+ex.getMessage());
	    	alert1.showAndWait();
	    	return "IOException";
        } 
        catch (ClassNotFoundException ex) { 
        	Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("ClassNotFoundException is caught! Cannot find Project class "+filename+"."+ex.getMessage());
	    	alert1.showAndWait();
	    	return "ClassNotFoundException";
        }
	}
	public void updateViewerPlot() {
		Project pj = getActiveProject();
		if (pj==null) return;
		pj.updateViewerPlot();
	}
	public String checkProjectName(String nameProject) {
		if (nameProject==null || nameProject.isEmpty())
			return "Empty project name!";
		else if (projectDict.containsKey(nameProject)){
			return "Duplicate project name!";
		}
		else {
			return null;
		}	
	}
	public String addProject(String nameProject) {
		String tmp = checkProjectName(nameProject);
		if (tmp!=null) return tmp;
		else {
			projectDict.put(nameProject, new Project(nameProject));
			activeProjKey = nameProject;
			return null;
		}	
	}
	public void setStepAsDefault(EnumStep es) {
		projectDict.get(activeProjKey).setProjectDefault(es);//no cloning, just reference
	}
	public Boolean isDefault() {
		if (!existCurrentProject()) return false;
		else return projectDict.get(activeProjKey).isDefault();
	}
	public void loadStepFromDefault(EnumStep es) {
		if (!existCurrentProject()) return;
		InputAgent ia = projectDict.get(activeProjKey).getProjectDefault(es);//already cloned in getProjectDefault()
		setStepAgent(es,ia);
	}
	public void addCalculation(String nameProject, EnumCalc ec) {
		if (nameProject==null || ec==null || nameProject.isEmpty()) return;
		if (!projectDict.containsKey(nameProject)) addProject(nameProject);//continue to add calc
		projectDict.get(nameProject).addCalculation(ec);
	}
	public void addCalcToActiveProj(EnumCalc ec) {
		if (activeProjKey==null|| ec==null || activeProjKey.isEmpty() || ! projectDict.containsKey(activeProjKey)) return;
		projectDict.get(activeProjKey).addCalculation(ec);
	}
	public void setActiveProject(String nameProject) {
		if (nameProject==null || nameProject.isEmpty() || projectDict == null)
			activeProjKey = null;
		else if (projectDict.containsKey(nameProject)){
			activeProjKey = nameProject;
		}
		else {
			
		}	
	}
	public void setActiveCalculation(EnumCalc ec) {
		if (existCurrentProject()) {
			projectDict.get(activeProjKey).setActiveCalcName(ec);
		}
	}
	public void setGeoActive(Boolean bl) {
		if (existCurrentProject()) {
			projectDict.get(activeProjKey).setGeoActive(bl);
		}
	}
	public Boolean existCurrentProject() {
		if (activeProjKey==null || activeProjKey.isEmpty() || projectDict==null || ! projectDict.containsKey(activeProjKey)) {
			return false;
		}
		else {
			return true;
		}
	}
	public Boolean existCurrentCalc() {
		if (!existCurrentProject()) return false;
		return projectDict.get(activeProjKey).existCurrentCalc();
	}
	public Boolean existCalcInCurrentProject(EnumCalc ec) {
		if (!existCurrentProject()) return false;
		return projectDict.get(activeProjKey).existCalc(ec);
	}
	public Boolean isCurrentCalc(EnumCalc ec) {
		if (!existCurrentCalc()) return false;//false, not null!
		return projectDict.get(activeProjKey).getActiveCalcName()==ec;
	}
	public Boolean existCurrentStep(EnumStep es) {
		if (!existCurrentCalc()) return false;
		return projectDict.get(activeProjKey).getActiveCalc().existStep(es);
	}
	public EnumCalc getCurrentCalcName() {
		if (!existCurrentCalc()) return null;
		return projectDict.get(activeProjKey).getActiveCalcName();
	}
	public ArrayList<EnumCalc> getCurrentCalcList(){
		if (!existCurrentProject()) return new ArrayList<EnumCalc>(); //return an empty list
		return projectDict.get(activeProjKey).getCalcList();
	}
	public InputAgent getStepAgent(EnumStep es) {
		if (!existCurrentCalc()) return null;
		return projectDict.get(activeProjKey).getActiveCalc().getAgent(es);
	}
	public void setStepAgent(EnumStep es,InputAgent ia) {
		if (!existCurrentCalc()) return;
		else projectDict.get(activeProjKey).getActiveCalc().setAgent(es,ia);
	}
	public InputAgentGeo getCurrentGeoAgent() {
		if (!existCurrentProject()) return null;
		return projectDict.get(activeProjKey).getAgentGeo();
	}
	public void setCurrentGeoInd(int ind) {
		if (!existCurrentProject()) return;
		projectDict.get(activeProjKey).setActiveGeoInd(ind);
	}
	public String removeProject(String nameProject) {
		if (nameProject==null || nameProject.isEmpty())
			return "Empty project name!";
		else if (projectDict.containsKey(nameProject)){
			projectDict.remove(nameProject);
			if (activeProjKey==nameProject){
				activeProjKey = getNextKey(nameProject);
			}
			return null;
		}
		else {
			return "No project named "+nameProject;
		}
	}
	private String getNextKey(String nameProject) {
		Boolean flag = false;
		if (!projectDict.isEmpty()){
			for (String key : projectDict.keySet()) {
				if (key == nameProject) {
					flag = true;
					continue;
				}
				if (flag) {
					return key;
				}
			}
		}
		return null;
	}
	public String getActiveProjectName() {
		if (projectDict==null || activeProjKey == null)  return null;
		if (projectDict.containsKey(activeProjKey)) 
		{
			return activeProjKey;
		}
		else {
			return null;
		}
	}
	public Project getActiveProject() {
		if (projectDict==null || activeProjKey == null || activeProjKey.isEmpty())  return null;
		if (projectDict.containsKey(activeProjKey)) 
		{
			Project pj = projectDict.get(activeProjKey);
			return pj;
		}
		else {
			return null;
		}
	}
	public QeInput getProjectCalcInp(String proj, EnumCalc calc, EnumStep indInp) {
		if (projectDict==null || activeProjKey == null || calc == null || indInp == null || proj == null|| 
				proj.isEmpty() )  return null;
		
		if (!projectDict.containsKey(proj)) return null;
		
		Project pj = projectDict.get(proj);
		if (pj==null) return null;
		
		calculationClass cc =  pj.getCalc(calc);
		if (cc==null) return null;
		
		QeInput qi = cc.getQeInput(indInp);
		if (qi==null) return null;
		
		return qi;
	}
	public QeInput getActiveProjectCalcInp(EnumCalc calc, EnumStep indInp) {
		if (projectDict==null || activeProjKey == null || calc == null || indInp == null)  return null;
		
		if (!projectDict.containsKey(activeProjKey)) return null;
		
		Project pj = projectDict.get(activeProjKey);
		if (pj==null) return null;
		
		calculationClass cc =  pj.getCalc(calc);
		if (cc==null) return null;
		
		QeInput qi = cc.getQeInput(indInp);
		if (qi==null) return null;
		
		return qi;
	}
	public void genInputFromAgent() {
		Project pj =  getActiveProject();
		if(pj==null) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setHeaderText("No project!");
	    	alert1.setContentText("No project!");
	    	alert1.showAndWait();
		}
		else pj.genInputFromAgent();
	}
	
}
