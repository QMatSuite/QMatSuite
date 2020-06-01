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

package app.input.geo;

import java.net.URL;
import java.util.ArrayList;
import java.util.ResourceBundle;
import com.consts.Constants.EnumFunctional;
import com.consts.Constants.EnumPP;
import com.pseudopot.EnumPseudoPotLib;
import com.pseudopot.PseudoDojoClass;
import com.pseudopot.SSSPClass;

import agent.InputAgentGeo;
import javafx.beans.binding.Bindings;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TableCell;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.cell.PropertyValueFactory;
import main.MainClass;

public class InputGeoElementsController implements Initializable{

	@FXML
    private Button defButton,buttonOpenLib;

	@FXML private TableView<Element> elementTable;
    
    @FXML private TableColumn<Element, Integer> indexColumn;
    
    @FXML private TableColumn<Element, Double> massColumn;
    
    @FXML private TableColumn<Element, String> nameColumn;
    
    @FXML private TableColumn<Element, String> pseudoColumn;

    @FXML
    private Label ppTypePoint,xcFuncPoint,ecutwfcPoint,ecutrhoPoint,labelPathPseudoLib;

    @FXML
    private Label ppTypeLabel,xcFuncLabel,ecutwfcLabel,ecutrhoLabel,relavLabel,relavPoint;

	
    @FXML private ComboBox<EnumFunctional> comboFunctional;
    
    @FXML private ComboBox<EnumPP> comboPP;
    
    @FXML private ComboBox<EnumPseudoPotLib> comboLib;
    
    @FXML private ComboBox<String> comboPrec;
    
    @FXML private CheckBox checkRelativ,resetCheck;
    
    private MainClass mainClass;
    
    private ObservableList<Element> elemData;
	
    private PseudoDojoClass pdClass;
    
    private SSSPClass ssspClass;
    
	public InputGeoElementsController(MainClass mc) {
		mainClass = mc;
		elemData = FXCollections.observableArrayList();
		pdClass = new PseudoDojoClass();
		ssspClass = new SSSPClass();
	}
    
    @Override
    public void initialize(URL location, ResourceBundle resources) {
    	initialize();
    }
    public void initialize() {
    	//pseudoPot library
    	ObservableList<EnumPseudoPotLib> typeLib = FXCollections.observableArrayList(EnumPseudoPotLib.values());
    	comboLib.setItems(typeLib);
    	
    	comboLib.getSelectionModel().selectedItemProperty().addListener((obs, oldSelect, newSelect) -> {
    		ObservableList<EnumFunctional> typeFunc;
    		ObservableList<EnumPP> typePP;
    		ObservableList<String> typePrec;
    		boolean bl;
    		
    		if(newSelect==null) return;
    		if(EnumPseudoPotLib.SSSP.equals(newSelect)) {
    			typeFunc = FXCollections.observableArrayList(ssspClass.getFunctionalList());
    			typePP = FXCollections.observableArrayList(ssspClass.getPpList());
    			typePrec = FXCollections.observableArrayList(ssspClass.getPrecisionList());
    			bl = ssspClass.getFullRelativSupport();
    		}
    		else if(EnumPseudoPotLib.PSEUDODOJO.equals(newSelect)) {
    			typeFunc = FXCollections.observableArrayList(pdClass.getFunctionalList());
    			typePP = FXCollections.observableArrayList(pdClass.getPpList());
    			typePrec = FXCollections.observableArrayList(pdClass.getPrecisionList());
    			bl = pdClass.getFullRelativSupport();
    		}
    		else {
    			return;
    		}
    		
    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (ia==null) return; 
			
			ia.typeLib=newSelect;
			
			//a bit complicated because needs to consider:
			//loading, don't want to overwrite things
			//user change library combobox
			//don't want to have empty selection
			EnumFunctional efTmp = ia.typeFunctional;
        	comboFunctional.setItems(typeFunc);comboFunctional.setDisable(typeFunc.isEmpty());
        	if(typeFunc.isEmpty()) {comboFunctional.getSelectionModel().clearSelection();}
        	else if (efTmp!=null && typeFunc.contains(efTmp)) {comboFunctional.getSelectionModel().select(efTmp);}
        	else {comboFunctional.getSelectionModel().select(0);}
        	
        	EnumPP epTmp = ia.typePP;
        	comboPP.setItems(typePP);comboPP.setDisable(typePP.isEmpty());
        	if(typePP.isEmpty()) {comboPP.getSelectionModel().clearSelection();}
        	else if (epTmp!=null && typePP.contains(epTmp)) {comboPP.getSelectionModel().select(epTmp);}
        	else {comboPP.getSelectionModel().select(0);}

        	Integer intTmp = ia.typePrec;
        	comboPrec.setItems(typePrec);comboPrec.setDisable(typePrec.isEmpty());
        	if(typePrec.isEmpty()) {comboPrec.getSelectionModel().clearSelection();}
        	else if (intTmp!=null && typePrec.size()>intTmp) {comboPrec.getSelectionModel().select(intTmp);}
        	else {comboPrec.getSelectionModel().select(0);}
        	

        	checkRelativ.setDisable(!bl);
        	if(!bl && checkRelativ.isSelected()) {checkRelativ.setSelected(false);}
        	
			updatePseudoElementList();
		});
    	//default use SSSP library, not necessary here
    	//comboLib.getSelectionModel().select(EnumPseudoPotLib.SSSP);
    	
    	//functional type
    	comboFunctional.setOnAction((event) -> {	
    		//if null, also take that
    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (ia!=null) ia.typeFunctional=comboFunctional.getValue();
			if (comboFunctional.getValue()!=null) {
				updatePseudoElementList();
			}
		});
    	//pp type
    	comboPP.setOnAction((event) -> {	
    		//if null, also take that
    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (ia!=null) ia.typePP=comboPP.getValue();
			if (comboPP.getValue()!=null) {
				updatePseudoElementList();
			}
			
		});
    	//precision type
    	comboPrec.setOnAction((event) -> {	
    		//if null, also take that
    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (ia!=null) ia.typePrec=comboPrec.getSelectionModel().getSelectedIndex();
			if (comboPrec.getValue()!=null) {
				updatePseudoElementList();
			}
		});
    	//full relativistic
    	checkRelativ.selectedProperty().addListener((obs, oldSelect, newSelect) -> {
    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (ia!=null) ia.isRelativ.setValue(newSelect);
			updatePseudoElementList();
		    //if (newSelect) comboPP.getSelectionModel().select(EnumPP.USPP);//no need to change ia.typePP explicitly
		});
    	//setup element table
    	setupTable();
    }
    private void updatePseudoElementList() {
    	InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
    	ArrayList<Element> elemListAll = iGeo.elemListAll;
    	if(elemListAll==null || elemListAll.isEmpty()) return;
    	
    	EnumPseudoPotLib eppl = comboLib.getSelectionModel().getSelectedItem();
    	if(eppl==null) return;
    	switch(eppl) {
    		case SSSP:
    			ssspClass.setPrecString(comboPrec.getSelectionModel().getSelectedItem());
    			break;
    		case PSEUDODOJO:
    			pdClass.setRelativ(checkRelativ.isSelected());
    			pdClass.setTypeFunctional(comboFunctional.getSelectionModel().getSelectedItem());
    			pdClass.setPrecString(comboPrec.getSelectionModel().getSelectedItem());
    			break;
    		default: return;
    	}
    	
    	for (Element ele : elemListAll) {
    		String pseudoPotFile;
    		switch(eppl) {
	    		case SSSP:pseudoPotFile=ssspClass.getFile(ele.getAtomSpecies().toString());break;
	    		case PSEUDODOJO:pseudoPotFile=pdClass.getFile(ele.getAtomSpecies().toString());break;
	    		default: return;
    		}
    		ele.setPseudoPotFile(pseudoPotFile);
    	}
    	
    	elemData.clear();
    	elemData.addAll(iGeo.elemListAll);
    }
    private void setupTable() {
    	indexColumn.setCellValueFactory(new PropertyValueFactory<Element, Integer>("index"));
    	indexColumn.setCellFactory(col -> {
		    TableCell<Element, Integer> cell = new TableCell<>();
		    cell.textProperty().bind(Bindings.createStringBinding(() -> {
		        if (cell.isEmpty()) {
		            return null ;
		        } else {
		            return Integer.toString(cell.getIndex()+1);
		        }
		    }, cell.emptyProperty(), cell.indexProperty()));
		    return cell ;
		});
    	nameColumn.setCellValueFactory(new PropertyValueFactory<Element, String>("atomSpecies"));
    	massColumn.setCellValueFactory(new PropertyValueFactory<Element, Double>("atomMass"));
    	pseudoColumn.setCellValueFactory(new PropertyValueFactory<Element, String>("pseudoPotFile"));
    	
    	elementTable.setItems(elemData);
		
    	elementTable.getSelectionModel().selectedItemProperty().addListener((obs, oldSelect, newSelect) -> {
		    //to be added
		});
    }
    public void loadProjectParameters() {
    	InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
		if (iGeo==null) return;
		//iGeo.updateElemListAll();//from atom generate elements table
		if (iGeo.typeLib==null) {comboLib.getSelectionModel().clearSelection();}
		else {comboLib.getSelectionModel().select(iGeo.typeLib);}
		//*************not efficient, run twice possible
		if (iGeo.typeFunctional==null) {comboFunctional.getSelectionModel().clearSelection();}
		else {comboFunctional.getSelectionModel().select(iGeo.typeFunctional);}
		if (iGeo.typePP==null) {comboPP.getSelectionModel().clearSelection();}
		else {comboPP.getSelectionModel().select(iGeo.typePP);}
		if (iGeo.typePrec==null) {comboPrec.getSelectionModel().clearSelection();}
		else {comboPrec.getSelectionModel().select(iGeo.typePrec);}
		checkRelativ.setSelected(iGeo.isRelativ.getValue());//should not be null!
//		elemData.clear();
//		elemData.addAll(iGeo.elemListAll);
		updatePseudoElementList();
    }
}
