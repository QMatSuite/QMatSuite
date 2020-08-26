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
package input;

import java.util.ArrayList;
import com.consts.Constants.EnumNameList;
import com.consts.Constants.EnumOptSchemeNeb;
import com.consts.Constants.EnumStep;
import com.consts.Constants.EnumStringMethod;

import agent.InputAgentGeo;
import agent.InputAgentNeb;
import agent.InputAgentScf;
import core.agent.WrapperString;
import core.com.error.InvalidKeyException;
import core.com.error.InvalidTypeException;
import core.com.error.ShowAlert;
import core.input.InputValueBoolean;
import core.input.InputValueDouble;
import core.input.InputValueInt;
import core.input.InputValueString;
import javafx.scene.control.Alert.AlertType;

public class NebInput extends QeInput{

	private PwInput pwInput;
	private ArrayList<InputAgentGeo> geoListCache = null;
	private int startGeoIndex = -1;
	private int endGeoIndex = -1;
	
	public NebInput() {
		super("neb");
		pwInput = new PwInput();
		
		sectionDict.put("PATH", new NameList(EnumNameList.PATH));
		sectionDict.get("PATH").setBoolRequired(true);
		sectionDict.get("PATH").addParameter("minimum_image", new InputValueBoolean("minimum_image",false,false));
		sectionDict.get("PATH").addParameter("string_method", new InputValueString("string_method","neb",false));
		sectionDict.get("PATH").addParameter("restart_mode", new InputValueString("restart_mode","from_scratch",false));
		sectionDict.get("PATH").addParameter("nstep_path", new InputValueInt("nstep_path",1,false));
		sectionDict.get("PATH").addParameter("num_of_images", new InputValueInt("num_of_images",0,true));
		sectionDict.get("PATH").addParameter("opt_scheme", new InputValueString("opt_scheme","quick-min",false));
		sectionDict.get("PATH").addParameter("CI_scheme", new InputValueString("CI_scheme","no-CI",false));
		sectionDict.get("PATH").addParameter("first_last_opt", new InputValueBoolean("first_last_opt",false,false));
		sectionDict.get("PATH").addParameter("ds", new InputValueDouble("ds",1.0,false));
		sectionDict.get("PATH").addParameter("path_thr", new InputValueDouble("path_thr",0.05,false));
	}
	
	@Override
	public void loadAgent(InputAgentScf ia1) {
		pwInput.loadAgent(ia1);
		pwInput.surpressAtomPositions();
	}
	public void loadAgent(ArrayList<InputAgentGeo> geoList) {
		geoListCache = geoList;
		pwInput.loadAgent(geoList.get(
				(startGeoIndex>=0 && startGeoIndex<geoList.size())?startGeoIndex:0));
	}
	@Override
	public void loadAgent(InputAgentNeb ia1) {
		startGeoIndex = ia1.startGeo;
		endGeoIndex = ia1.endGeo;
		try {
			setValue("PATH","minimum_image",ia1.boolMinImage);
			setValue("PATH","string_method",new WrapperString(((EnumStringMethod)ia1.enumMethod.getValue()).getName(),ia1.enumMethod.isEnabled()));
			setValue("PATH","restart_mode",new WrapperString(ia1.boolRestart.getValue()?"restart":"from_scratch",ia1.boolRestart.isEnabled()));
			
			setValue("PATH","nstep_path",ia1.nstepPath);//not QE default
			setValue("PATH","num_of_images",ia1.numOfImages);//not QE default
			setRequiredAndWrite("PATH","nstep_path",true,true);//not required, but safer
			setRequiredAndWrite("PATH","num_of_images",true,true);//not required, but safer
			
			setValue("PATH","opt_scheme",new WrapperString(((EnumOptSchemeNeb)ia1.enumOptScheme.getValue()).getName(),ia1.enumOptScheme.isEnabled()));
			setValue("PATH","CI_scheme",new WrapperString(ia1.boolCI.getValue()?"auto":"no-CI",ia1.boolCI.isEnabled()));
			setValue("PATH","first_last_opt",ia1.firstLastOpt);
			setValue("PATH","ds",ia1.ds);
			setValue("PATH","path_thr",ia1.pathThr);

		} catch (InvalidKeyException | InvalidTypeException e) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Exception!"+e.getMessage());
			e.printStackTrace();
		}
	}
	@Override
	public ContainerInputString genInput(EnumStep es) {
		//ContainerInputString ci = genInput("!"+es.toString()+"\n");
		ContainerInputString ci = genInput("");
		ci.stepName = es;//necessary!
		ci.appendLog(errorMessage);
		return ci;
	} 
	@Override
	public ContainerInputString genInput(String startingMsg) {
		ContainerInputString ci = new ContainerInputString();
		
		//construct input file
		ci.appendInput(startingMsg);
		ci.appendInput("BEGIN\n");
		ci.appendInput("BEGIN_PATH_INPUT\n");
		NameList nml = (NameList) sectionDict.get("PATH");
		ContainerInputString ciNeb = nml.toStringWrapper();
		
		pwInput.surpressCalculationType();
		ContainerInputString ciScf = pwInput.genInput("");
        ci.append(ciNeb);
        ci.appendInput("END_PATH_INPUT\n");
        ci.appendInput("BEGIN_ENGINE_INPUT\n");
        ci.append(ciScf);
        
        ci.appendInput("BEGIN_POSITIONS\n");
        
        if(geoListCache!=null && !geoListCache.isEmpty()) {
        	ci.appendInput("FIRST_IMAGE\n");
        	if(startGeoIndex>=0 && startGeoIndex<geoListCache.size()) {
        		pwInput.loadAgent(geoListCache.get(startGeoIndex));//load twice, not ideally efficient
        		ci.append(pwInput.genAtomPositionInput());
        	}
        	else {
        		ci.appendLog("First geometry out of index.\n");
        	}
        	
    		ci.appendInput("LAST_IMAGE\n");
    		if(endGeoIndex>=0 && endGeoIndex<geoListCache.size()) {
    			pwInput.loadAgent(geoListCache.get(endGeoIndex));
    			ci.append(pwInput.genAtomPositionInput());
        	}
    		else {
        		ci.appendLog("Second geometry out of index.\n");
        	}
        }
        else {
        	ci.appendLog("Geometry list null or empty.\n");
        }
        
        
        ci.appendInput("END_POSITIONS\n");
        ci.appendInput("END_ENGINE_INPUT\n");
        ci.appendInput("END\n");
        
        ci.commandName = this.commandName;
		return ci;
	}  
}
